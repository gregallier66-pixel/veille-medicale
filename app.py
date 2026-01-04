import streamlit as st
import requests
import google.generativeai as genai

# Configuration
st.set_page_config(page_title="Veille Medicale", layout="wide")

# Lecture des clés dans les Secrets (Vérifiez bien l'orthographe dans l'onglet Secrets)
# Ils doivent s'appeler GEMINI_KEY et PUBMED_API_KEY
K1 = st.secrets.get("AIzaSyCMPYJIHZ83uVhYwV6eqKxsC1pv7Hbol6g", "")
K2 = st.secrets.get("17626ab73380b71515000371bdcee0c26308", "")

st.title("🩺 Ma Veille Médicale")

spec = st.sidebar.selectbox("Specialite", ["Endocrinologie", "Gynecologie", "Medecine Generale"])

if st.button(f"Analyser {spec}"):
    if not K1:
        st.error("Cle API manquante dans les Secrets Streamlit.")
    else:
        with st.spinner("Recherche en cours..."):
            # Recherche simple
            url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {"db": "pubmed", "term": spec, "retmode": "json", "retmax": 3, "api_key": K2}
            
            res = requests.get(url, params=params).json()
            ids = res.get("esearchresult", {}).get("idlist", [])
            
            if ids:
                genai.configure(api_key=K1)
                model = genai.GenerativeModel('gemini-1.5-flash')
                links = [f"https://pubmed.ncbi.nlm.nih.gov/{i}/" for i in ids]
                
                response = model.generate_content(f"Resume en Francais : {links}")
                st.markdown(response.text)
            else:
                st.write("Aucun article trouvé.")
