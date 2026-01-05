import streamlit as st
import google.generativeai as genai
import requests
import json

st.set_page_config(page_title="Veille Médicale", layout="wide")

# Récupération des secrets
try:
    G_KEY = st.secrets["GEMINI_KEY"]
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
        
        # PAS DE CLÉ API - fonctionne parfaitement sans
        
        with st.expander("🔍 Informations de requête"):
            st.write("**URL:**", base_url)
            st.write("**Paramètres:**")
            st.json(params)
        
        try:
            response = requests.get(
                base_url,
                params=params,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Streamlit Medical App)',
                },
                timeout=15
            )
            
            with st.expander("📋 Réponse HTTP"):
                st.write(f"**Status Code:** {response.status_code}")
                st.write(f"**URL finale:** {response.url}")
            
            if response.status_code != 200:
                st.error(f"❌ Erreur HTTP {response.status_code}")
                st.code(response.text)
                st.stop()
            
            data = response.json()
            
            with st.expander("📊 Données JSON complètes"):
                st.json(data)
            
            ids = data.get("esearchresult", {}).get("idlist", [])
            count = data.get("esearchresult", {}).get("count", "0")
            
            st.info(f"📊 PubMed a trouvé {count} articles au total")
            
            if ids:
                st.success(f"✅ {len(ids)} articles récupérés")
                
                st.subheader("📚 Articles trouvés")
                for i, pmid in enumerate(ids, 1):
                    st.markdown(f"{i}. [Article PubMed {pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)")
                
                st.subheader("🤖 Analyse par Gemini")
                with st.spinner("Génération de la synthèse médicale..."):
                    try:
                        genai.configure(api_key=G_KEY)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        liens = "\n".join([f"- https://pubmed.ncbi.nlm.nih.gov/{i}/" for i in ids])
                        
                        prompt = f"""Tu es un expert médical francophone spécialisé en {spec_fr}.

Analyse ces {len(ids)} articles médicaux récents de {annee} (PMIDs: {', '.join(ids)}).

Rédige une synthèse professionnelle en français avec:

## 📊 Vue d'ensemble
Contexte général des publications

## 🔬 Tendances principales
Thématiques émergentes et approches innovantes

## 💡 Découvertes notables
Résultats significatifs et avancées marquantes

## 🏥 Implications cliniques
Applications pratiques et recommandations

**Articles:**
{liens}

Sois précis, scientifique et accessible."""
                        
                        res_ia = model.generate_content(prompt)
                        st.markdown(res_ia.text)
                        
                    except Exception as e:
                        st.error(f"❌ Erreur lors de l'analyse IA: {str(e)}")
                        st.info("💡 Consultez les articles directement via les liens ci-dessus")
            else:
                st.warning(f"⚠️ Aucun article trouvé pour '{term}' en {annee}")
                st.info("💡 Essayez une autre année ou spécialité")
        
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Erreur de connexion: {str(e)}")
            
        except json.JSONDecodeError as e:
            st.error(f"❌ Erreur JSON: {str(e)}")
            st.code(response.text)
            
        except Exception as e:
            st.error(f"❌ Erreur: {type(e).__name__} - {str(e)}")
            import traceback
            with st.expander("Détails"):
                st.code(traceback.format_exc())
