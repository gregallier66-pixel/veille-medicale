import streamlit as st
import google.generativeai as genai
import requests

st.set_page_config(page_title="Veille Médicale", layout="wide")

# Récupération des secrets
try:
    G_KEY = st.secrets["GEMINI_KEY"]
    P_KEY = st.secrets["PUBMED_API_KEY"]
except:
    st.error("Erreur de Secrets dans Streamlit.")
    st.stop()

# Traduction pour PubMed
TRAD = {"Gynécologie": "Gynecology", "Endocrinologie": "Endocrinology", "Médecine Générale": "General Medicine"}

st.title("🩺 Veille Médicale Expert")

with st.sidebar:
    st.header("Paramètres")
    spec_fr = st.selectbox("Spécialité", list(TRAD.keys()))
    annee = st.radio("Année", ["2024", "2025"])
    nb = st.slider("Articles", 1, 10, 5)

if st.button(f"Rechercher en {spec_fr}"):
    with st.spinner("Appel à PubMed..."):
        term = TRAD[spec_fr]
        # Requête PubMed ultra-basique
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={term}+AND+{annee}[dp]&retmode=json&retmax={nb}&api_key={P_KEY}"
        
        # Ajout d'un en-tête pour éviter d'être bloqué
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        try:
            response = requests.get(url, headers=headers)
            data = response.json()
            ids = data.get("esearchresult", {}).get("idlist", [])
            
            if ids:
                st.success(f"Trouvé {len(ids)} articles ! Analyse IA...")
                genai.configure(api_key=G_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                liens = [f"https://pubmed.ncbi.nlm.nih.gov/{i}/" for i in ids]
                prompt = f"Résume en français de façon très médicale ces articles : {liens}"
                
                res_ia = model.generate_content(prompt)
                st.markdown(res_ia.text)
            else:
                # Si PubMed répond 0, on affiche l'URL pour comprendre pourquoi
                st.warning(f"PubMed ne renvoie rien pour {term}. Voici l'URL testée :")
                st.code(url)
        except Exception as e:
            st.error(f"Erreur : {e}")
