import streamlit as st
import google.generativeai as genai
import requests
import json

st.set_page_config(page_title="Veille Médicale", layout="wide")

# Récupération des secrets
try:
    G_KEY = st.secrets["GEMINI_KEY"]
    P_KEY = st.secrets.get("PUBMED_API_KEY", "")  # Optionnel
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
        
        # Construction de la requête - MÉTHODE SIMPLE ET FIABLE
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        
        # Paramètres minimaux qui fonctionnent à coup sûr
        params = {
            "db": "pubmed",
            "term": f"{term} {annee}",  # Simplifié sans [PDAT]
            "retmode": "json",
            "retmax": nb,
            "sort": "relevance"
        }
        
        # Ajouter la clé API seulement si elle existe
        if P_KEY and len(P_KEY) > 10:
            params["api_key"] = P_KEY
        
        # Affichage pour débogage
        with st.expander("🔍 Informations de requête"):
            st.write("**URL:**", base_url)
            st.write("**Paramètres:**")
            st.json(params)
        
        try:
            # Utiliser requests au lieu de urllib (plus fiable)
            response = requests.get(
                base_url,
                params=params,
                headers={
                    'User-Agent': 'Mozilla/5.0',
                },
                timeout=15
            )
            
            # Afficher la réponse brute
            with st.expander("📋 Réponse HTTP"):
                st.write(f"**Status Code:** {response.status_code}")
                st.write(f"**URL finale:** {response.url}")
                st.code(response.text[:500])  # Premiers 500 caractères
            
            # Vérifier le statut
            if response.status_code != 200:
                st.error(f"❌ Erreur HTTP {response.status_code}")
                st.write("**Réponse complète:**")
                st.code(response.text)
                st.stop()
            
            # Parser la réponse JSON
            data = response.json()
            
            # Afficher la structure complète
            with st.expander("📊 Données JSON complètes"):
                st.json(data)
            
            # Extraire les IDs
            ids = data.get("esearchresult", {}).get("idlist", [])
            count = data.get("esearchresult", {}).get("count", "0")
            
            st.info(f"📊 PubMed a trouvé {count} articles au total")
            
            if ids:
                st.success(f"✅ Affichage de {len(ids)} articles")
                
                # Affichage des liens
                st.subheader("📚 Articles trouvés")
                cols = st.columns(2)
                for i, pmid in enumerate(ids):
                    col = cols[i % 2]
                    with col:
                        st.markdown(f"**{i+1}.** [PubMed ID: {pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)")
                
                # Analyse IA
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
```

## Changements clés :

1. ✅ **Utilisation de `requests`** au lieu de `urllib` (plus fiable et simple)
2. ✅ **Requête simplifiée** : `term: "Gynecology 2024"` au lieu de syntaxe complexe
3. ✅ **Clé API optionnelle** : fonctionne sans (avec rate limiting)
4. ✅ **Débogage complet** : affiche URL finale, status code, réponse brute

## Installation de `requests` :

Ajoutez dans votre `requirements.txt` :
```
streamlit
google-generativeai
requests
