import streamlit as st
import requests
import google.generativeai as genai
import os

# Configuration de l'interface
st.set_page_config(page_title="Veille Médicale Expert", page_icon="🩺", layout="wide")

# Récupération sécurisée des secrets
GEMINI_KEY = st.secrets.get("AIzaSyCMPYJIHZ83uVhYwV6eqKxsC1pv7Hbol6g", "")
PUBMED_API_KEY = st.secrets.get("17626ab73380b71515000371bdcee0c26308", "")

st.title("🩺 Ma Veille Médicale Interactive")

# Barre latérale
with st.sidebar:
    st.header("Filtres")
    specialite = st.selectbox("Spécialité", ["Gynécologie-Obstétrique", "Endocrinologie", "Médecine Générale"])
    nb_resultats = st.slider("Nombre d'articles", 1, 10, 5)

# Requête PubMed
query = f"{specialite}[Title] AND 2025[Date - Publication]"

if st.button(f"Lancer la veille en {specialite}"):
    if not GEMINI_KEY:
        st.error("Erreur : La clé GEMINI_KEY n'est pas détectée dans les Secrets Streamlit.")
    else:
        with st.spinner("Analyse PubMed et IA en cours..."):
            # Recherche PubMed
            url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": nb_resultats, "api_key": PUBMED_API_KEY}
            
            try:
                ids = requests.get(url, params=params).json().get("esearchresult", {}).get("idlist", [])
                
                if ids:
                    genai.configure(api_key=GEMINI_KEY)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    
                    liens = [f"https://pubmed.ncbi.nlm.nih.gov/{i}/" for i in ids]
                    prompt = f"Fais une synthèse en Français pour un médecin de ces articles : {liens}"
                    
                    response = model.generate_content(prompt)
                    st.markdown(response.text)
                else:
                    st.warning("Aucun article trouvé aujourd'hui.")
            except Exception as e:
                st.error(f"Une erreur est survenue : {e}")

