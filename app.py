import streamlit as st
import google.generativeai as genai
import urllib.request
import urllib.parse
import json

st.set_page_config(page_title="Veille Médicale Expert", layout="wide")

try:
    G_KEY = st.secrets["GEMINI_KEY"]
    P_KEY = st.secrets["PUBMED_API_KEY"]
except:
    st.error("Secrets manquants.")
    st.stop()

TRAD = {"Gynécologie": "Gynecology", "Endocrinologie": "Endocrinology", "Médecine Générale": "General Medicine"}

st.title("🩺 Ma Veille Médicale")

with st.sidebar:
    spec_fr = st.selectbox("Spécialité", list(TRAD.keys()))
    annee = st.radio("Année", ["2024", "2025"])
    nb = st.slider("Articles", 1, 5, 2) # Limité à 5 pour la rapidité

if st.button("Lancer la recherche"):
    # Étape 1 : PubMed
    status = st.empty() 
    status.info("1. Recherche sur PubMed en cours...")
    
    term = TRAD[spec_fr]
    params = {"db": "pubmed", "term": f"{term} AND {annee}[pdat]", "retmode": "json", "retmax": nb, "api_key": P_KEY}
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{urllib.parse.urlencode(params)}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            ids = data.get("esearchresult", {}).get("idlist", [])
        
        if ids:
            status.info(f"2. {len(ids)} articles trouvés. Analyse IA lancée...")
            # Étape 2 : IA
            genai.configure(api_key=G_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            liens = [f"https://pubmed.ncbi.nlm.nih.gov/{i}/" for i in ids]
            
            prompt = f"Résume brièvement en français ces articles médicaux : {liens}"
            response = model.generate_content(prompt)
            
            status.empty() # On efface le message de chargement
            st.success("Analyse terminée !")
            st.markdown(response.text)
        else:
            status.warning("Aucun article trouvé.")
    except Exception as e:
        st.error(f"Erreur : {e}")
