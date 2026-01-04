import streamlit as st
import google.generativeai as genai
import requests

# 1. RECUPERATION FORCEE DES SECRETS
# On utilise st.secrets pour lire directement le coffre-fort de Streamlit
try:
    G_KEY = st.secrets["AIzaSyCMPYJIHZ83uVhYwV6eqKxsC1pv7Hbol6g"]
    P_KEY = st.secrets["17626ab73380b71515000371bdcee0c26308"]
except:
    st.error("ERREUR CRITIQUE : Les noms GEMINI_KEY ou PUBMED_API_KEY sont mal orthographiés dans l'onglet Secrets.")
    st.stop()

st.title("🩺 Ma Veille Médicale")

# 2. INTERFACE
spec = st.sidebar.selectbox("Spécialité", ["Endocrinologie", "Gynécologie", "Médecine Générale"])

if st.button(f"Lancer l'analyse en {spec}"):
    with st.spinner("IA en cours d'analyse..."):
        # Configuration Gemini
        genai.configure(api_key=G_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Test rapide sur PubMed
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {"db": "pubmed", "term": spec, "retmode": "json", "retmax": 2, "api_key": P_KEY}
        
        try:
            r = requests.get(url, params=params).json()
            ids = r.get("esearchresult", {}).get("idlist", [])
            
            if ids:
                prompt = f"Fais un résumé médical en français des IDs PubMed suivants : {ids}"
                response = model.generate_content(prompt)
                st.success("Analyse terminée !")
                st.markdown(response.text)
            else:
                st.info("Aucun article récent trouvé pour cette spécialité.")
        except Exception as e:
            st.error(f"Erreur technique : {e}")
