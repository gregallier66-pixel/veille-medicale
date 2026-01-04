import streamlit as st
import google.generativeai as genai
import requests
from datetime import datetime, timedelta

# Configuration
st.set_page_config(page_title="Veille Médicale", layout="wide")

# Récupération des secrets
try:
    G_KEY = st.secrets["GEMINI_KEY"]
    P_KEY = st.secrets["PUBMED_API_KEY"]
except:
    st.error("Erreur de Secrets. Vérifiez l'onglet Secrets sur Streamlit.")
    st.stop()

st.title("🩺 Ma Veille Médicale Expert")

# Barre latérale avec tous vos réglages
with st.sidebar:
    st.header("Configuration")
    spec = st.selectbox("Spécialité", ["Gynécologie", "Endocrinologie", "Médecine Générale"])
    periode = st.radio("Période", ["Dernières 24h", "Depuis 2024", "Depuis 2025"])
    nb_art = st.slider("Nombre d'articles", 1, 10, 5)

# Logique de date pour PubMed
if periode == "Dernières 24h":
    date_query = (datetime.now() - timedelta(days=1)).strftime("%Y/%m/%d")
elif periode == "Depuis 2024":
    date_query = "2024/01/01"
else:
    date_query = "2025/01/01"

if st.button(f"Lancer la veille en {spec}"):
    with st.spinner("Recherche PubMed et Analyse IA..."):
        # Construction de la requête
        query = f"{spec}[Title/Abstract] AND {date_query}[Date - Publication] : 3000[Date - Publication]"
        
        u = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": nb_art, "api_key": P_KEY}
        
        try:
            r = requests.get(u, params=params).json()
            ids = r.get("esearchresult", {}).get("idlist", [])
            
            if ids:
                genai.configure(api_key=G_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                links = [f"https://pubmed.ncbi.nlm.nih.gov/{i}/" for i in ids]
                
                prompt = f"Agis en tant qu'expert médical. Résume de façon structurée en français les articles suivants : {links}"
                response = model.generate_content(prompt)
                st.success(f"{len(ids)} articles analysés !")
                st.markdown(response.text)
            else:
                st.warning(f"Aucun article trouvé pour '{spec}' depuis le {date_query}. Essayez une période plus large.")
        except Exception as e:
            st.error(f"Erreur : {e}")
