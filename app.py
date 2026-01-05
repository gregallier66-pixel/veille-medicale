import streamlit as st
import google.generativeai as genai
import requests
import json

st.set_page_config(page_title="Veille Médicale", layout="wide")

# Récupération des secrets
try:
    G_KEY = st.secrets["GEMINI_KEY"]
    P_KEY = st.secrets.get("PUBMED_API_KEY", "")
except:
    st.error("Erreur de Secrets. Vérifiez GEMINI_KEY.")
    st.stop()

TRAD = {
    "Gynécologie": "Gynecology", 
    "Endocrinologie": "Endocrinology", 
    "Médecine Générale": "General Medicine"
}

st.title("🩺 Ma Veille Médicale Expert")

with st.sidebar:
    st.header("Configuration")
    spec_fr = st.selectbox("Spécialité", list(TRAD.keys()))
    annee = st.radio("Année", ["2024", "2025"])
    nb = st.slider("Articles", 1, 10, 5)

if st.button("Lancer la recherche", key="unique_search_button"):
    with st.spinner("Interrogation de PubMed..."):
        term = TRAD[spec_fr]
        
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        
        params = {
            "db": "pubmed",
            "term": f"{term} {annee}",
            "retmode": "json",
            "retmax": nb,
            "sort": "relevance"
        }
        
        if P_KEY and len(P_KEY) > 10:
            params["api_key"] = P_KEY
        
        with st.expander("🔍 Informations de requête"):
            st.write("**URL:**", base_url)
            st.write("**Paramètres:**")
            st.json(params)
        
        try:
            response = requests.get(
                base_url,
                params=params,
                headers={
                    'User-Agent': 'Mozilla/5.0',
                },
                timeout=15
            )
            
            with st.expander("📋 Réponse HTTP"):
                st.write(f"**Status Code:** {response.status_code}")
                st.write(f"**URL finale:** {response.url}")
                st.code(response.text[:500])
            
            if response.status_code != 200:
                st.error(f"❌ Erreur HTTP {response.status_code}")
                st.write("**Réponse complète:**")
                st.code(response.text)
                st.stop()
            
            data = response.json()
            
            with st.expander("📊 Données JSON complètes"):
                st.json(data)
            
            ids = data.get("esearchresult", {}).get("idlist", [])
            count = data.get("esearchresult", {}).get("count", "0")
            
            st.info(f"📊 PubMed a trouvé {count} articles au total")
            
            if ids:
                st.success(f"✅ Affichage de {len(ids)} articles")
                
                st.subheader("📚 Articles trouvés")
                cols = st.columns(2)
                for i, pmid in enumerate(ids):
                    col = cols[i % 2]
                    with col:
                        st.markdown(f"**{i+1}.** [PubMed ID: {pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)")
                
                st.subheader("🤖 Analyse par IA")
                with st.spinner("Génération du résumé..."):
                    try:
                        genai.configure(api_key=G_KEY)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        liens = "\n".join([f"- https://pubmed.ncbi.nlm.nih.gov/{i}/" for i in ids])
                        
                        prompt = f"""Tu es un expert médical francophone spécialisé en {spec_fr}.

Tu dois analyser {len(ids)} articles médicaux récents de {annee} identifiés sur PubMed.

PMIDs: {', '.join(ids)}

Rédige une synthèse professionnelle en français structurée ainsi:

## 📊 Vue d'ensemble
- Contexte et portée des publications

## 🔬 Tendances principales
- Les thématiques émergentes
- Les approches innovantes

## 💡 Découvertes notables
- Les résultats significatifs
- Les avancées marquantes

## 🏥 Implications cliniques
- Applications pratiques
- Recommandations potentielles

**Liens vers les articles:**
{liens}

Sois précis, scientifique et accessible."""
                        
                        res_ia = model.generate_content(prompt)
                        st.markdown(res_ia.text)
                        
                    except Exception as e:
                        st.error(f"❌ Erreur IA: {str(e)}")
                        st.info("💡 Vous pouvez consulter les articles directement via les liens ci-dessus")
            else:
                st.warning(f"⚠️ Aucun article trouvé pour '{term}' en {annee}")
                st.info("💡 **Suggestions:**")
                st.write("- Essayez une autre année")
                st.write("- Changez de spécialité")
                st.write("- La recherche peut être trop restrictive")
        
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Erreur de connexion: {str(e)}")
            st.info("Vérifiez votre connexion Internet")
            
        except json.JSONDecodeError as e:
            st.error(f"❌ Erreur JSON: {str(e)}")
            st.write("La réponse n'est pas au format JSON valide")
            st.code(response.text)
            
        except Exception as e:
            st.error(f"❌ Erreur: {type(e).__name__}")
            st.write(str(e))
            import traceback
            with st.expander("Détails techniques"):
                st.code(traceback.format_exc())
