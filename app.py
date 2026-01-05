import streamlit as st
import google.generativeai as genai
import urllib.request
import json

st.set_page_config(page_title="Veille Médicale Expert", layout="wide")

# Récupération sécurisée des secrets
try:
    G_KEY = st.secrets["GEMINI_KEY"]
    P_KEY = st.secrets["PUBMED_API_KEY"]
except:
    st.error("Erreur de Secrets dans Streamlit.")
    st.stop()

# Dictionnaire de recherche
TRAD = {"Gynécologie": "Gynecology", "Endocrinologie": "Endocrinology", "Médecine Générale": "General Medicine"}

st.title("🩺 Veille Médicale Expert")

with st.sidebar:
    st.header("Paramètres")
    spec_fr = st.selectbox("Spécialité", list(TRAD.keys()))
    annee = st.radio("Année", ["2024", "2025"])
    nb = st.slider("Articles", 1, 10, 5)

if st.button(f"Lancer la recherche"):
    with st.spinner("Connexion sécurisée à PubMed..."):
        term = TRAD[spec_fr]
        # URL de recherche simplifiée
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={term}+AND+{annee}[dp]&retmode=json&retmax={nb}&api_key={P_KEY}"
        
        try:
            # On force une identification de type 'Navigateur'
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                ids = data.get("esearchresult", {}).get("idlist", [])
            
            if ids:
                st.success(f"✅ {len(ids)} articles identifiés. Analyse par l'IA...")
                genai.configure(api_key=G_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                liens = [f"https://pubmed.ncbi.nlm.nih.gov/{i}/" for i in ids]
                prompt = f"Tu es un expert médical. Résume en français ces articles récents de façon structurée : {liens}"
                
                res_ia = model.generate_content(prompt)
                st.markdown(res_ia.text)
            else:
                st.warning(f"PubMed ne renvoie aucun résultat pour {term} en {annee}.")
                st.info("Astuce : Si PubMed bloque, essayez de changer de spécialité pour tester.")
                
        except Exception as e:
            st.error(f"Erreur de connexion : {e}")
