import streamlit as st
import google.generativeai as genai
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="Veille Médicale", layout="wide")

# Secrets
try:
    G_KEY = st.secrets["GEMINI_KEY"]
    P_KEY = st.secrets["PUBMED_API_KEY"]
except:
    st.error("Erreur de Secrets.")
    st.stop()

# Dictionnaire de traduction pour PubMed
TRADUCTION = {
    "Gynécologie": "Gynecology",
    "Endocrinologie": "Endocrinology",
    "Médecine Générale": "General Medicine"
}

st.title("🩺 Ma Veille Médicale Expert")

with st.sidebar:
    st.header("Configuration")
    spec_fr = st.selectbox("Spécialité", list(TRADUCTION.keys()))
    periode = st.radio("Période", ["Dernières 24h", "Depuis 2024", "Depuis 2025"])
    nb_art = st.slider("Nombre d'articles", 1, 10, 5)

# Mapping des dates
if periode == "Dernières 24h":
    date_query = (datetime.now() - timedelta(days=2)).strftime("%Y/%m/%d")
else:
    date_query = "2024/01/01" if periode == "Depuis 2024" else "2025/01/01"

if st.button(f"Lancer la veille en {spec_fr}"):
    with st.spinner("Interrogation de PubMed (USA)..."):
        # On utilise le terme anglais pour la recherche
        term_en = TRADUCTION[spec_fr]
        query = f"{term_en}[Title/Abstract] AND {date_query}[Date - Publication] : 3000[Date - Publication]"
        
        u = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": nb_art, "api_key": P_KEY}
        
        try:
            r = requests.get(u, params=params).json()
            ids = r.get("esearchresult", {}).get("idlist", [])
            
            if ids:
                st.info(f"Trouvé : {len(ids)} articles. L'IA les analyse en français...")
                genai.configure(api_key=G_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # Récupération des titres pour l'IA
                links = [f"https://pubmed.ncbi.nlm.nih.gov/{i}/" for i in ids]
                prompt = f"Tu es un expert médical. Voici des liens d'articles : {links}. Fais un résumé structuré et pertinent en français pour chaque article."
                
                response = model.generate_content(prompt)
                st.markdown(response.text)
            else:
                st.warning(f"Toujours rien trouvé pour '{term_en}' depuis le {date_query}. Essayez la période 'Depuis 2024'.")
        except Exception as e:
            st.error(f"Erreur technique : {e}")
