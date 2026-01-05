import streamlit as st
import requests
import json
import time

st.set_page_config(page_title="Veille Médicale", layout="wide")

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

if st.button("Lancer la recherche"):
    
    term = TRAD[spec_fr]
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
        with st.spinner("Connexion à PubMed..."):
            response = requests.get(
                base_url,
                params=params,
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=10
            )
        
        if response.status_code == 200:
            data = response.json()
            search_result = data.get("esearchresult", {})
            ids = search_result.get("idlist", [])
            count = search_result.get("count", "0")
            
            st.success(f"✅ {count} articles trouvés - Affichage de {len(ids)}")
            
            if ids:
                st.subheader("📚 Articles récents")
                
                for i, pmid in enumerate(ids, 1):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**{i}.** [Article PubMed ID: {pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)")
                    with col2:
                        st.link_button("📖 Lire", f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
                
                st.divider()
                st.info("💡 **Synthèse IA disponible après configuration de la clé Gemini**")
                st.write("Pour activer l'analyse IA :")
                st.write("1. Obtenez une clé sur https://aistudio.google.com/apikey")
                st.write("2. Ajoutez-la dans Settings → Secrets → GEMINI_KEY")
            else:
                st.warning(f"Aucun article trouvé pour {term} en {annee}")
        else:
            st.error(f"Erreur HTTP {response.status_code}")
    
    except Exception as e:
        st.error(f"Erreur: {str(e)}")

st.markdown("---")
st.caption("🔬 Données fournies par PubMed/NCBI")
