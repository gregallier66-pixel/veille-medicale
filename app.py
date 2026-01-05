import streamlit as st
import google.generativeai as genai
import requests
import json
import time

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
    
    term = TRAD[spec_fr]
    
    # URL et paramètres
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    
    params = {
        "db": "pubmed",
        "term": f"{term} {annee}",
        "retmode": "json",
        "retmax": nb,
        "sort": "relevance"
    }
    
    st.info(f"🔍 Recherche: {term} en {annee}")
    
    try:
        # TENTATIVE 1: Requête avec timeout court
        with st.spinner("Connexion à PubMed..."):
            start_time = time.time()
            
            response = requests.get(
                base_url,
                params=params,
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=10  # Timeout de 10 secondes
            )
            
            elapsed = time.time() - start_time
            st.success(f"✅ Réponse reçue en {elapsed:.1f}s")
        
        # Vérifier le status
        if response.status_code != 200:
            st.error(f"❌ Erreur HTTP {response.status_code}")
            with st.expander("Détails"):
                st.code(response.text)
            st.stop()
        
        # Parser JSON
        data = response.json()
        
        # Afficher résultat brut
        with st.expander("📊 Réponse PubMed"):
            st.json(data)
        
        # Extraire les IDs
        search_result = data.get("esearchresult", {})
        ids = search_result.get("idlist", [])
        count = search_result.get("count", "0")
        
        st.info(f"📊 Total trouvé: {count} articles")
        
        if ids:
            st.success(f"✅ {len(ids)} articles affichés")
            
            # Afficher les liens
            st.subheader("📚 Articles")
            for i, pmid in enumerate(ids, 1):
                st.markdown(f"{i}. [PubMed {pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)")
            
            # Analyse IA
            st.subheader("🤖 Synthèse IA")
            
            with st.spinner("Génération en cours..."):
                try:
                    genai.configure(api_key=G_KEY)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    
                    liens_texte = "\n".join([f"- https://pubmed.ncbi.nlm.nih.gov/{i}/" for i in ids])
                    
                    prompt = f"""Synthèse médicale en français pour {spec_fr} - {annee}

PMIDs: {', '.join(ids)}

Rédige une analyse structurée:

**Vue d'ensemble**: Contexte général
**Tendances**: Thématiques émergentes  
**Découvertes**: Résultats importants
**Implications**: Applications cliniques

Liens: {liens_texte}"""
                    
                    response_ia = model.generate_content(prompt)
                    st.markdown(response_ia.text)
                    
                except Exception as e:
                    st.error(f"Erreur IA: {str(e)}")
        else:
            st.warning(f"⚠️ Aucun résultat pour '{term}' en {annee}")
            st.info("💡 Essayez une autre année")
    
    except requests.exceptions.Timeout:
        st.error("❌ Timeout: PubMed ne répond pas")
        st.info("Réessayez dans quelques secondes")
        
    except requests.exceptions.ConnectionError:
        st.error("❌ Erreur de connexion Internet")
        
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Erreur réseau: {str(e)}")
        
    except json.JSONDecodeError:
        st.error("❌ Réponse invalide de PubMed")
        with st.expander("Réponse brute"):
            st.code(response.text)
        
    except Exception as e:
        st.error(f"❌ Erreur: {type(e).__name__}")
        st.write(str(e))

st.markdown("---")
st.caption("💡 Veille médicale propulsée par PubMed et Gemini")
