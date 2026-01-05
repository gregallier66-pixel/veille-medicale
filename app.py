import streamlit as st
import google.generativeai as genai
import urllib.request
import urllib.parse
import json

st.set_page_config(page_title="Veille Médicale", layout="wide")

# Récupération des secrets
try:
    G_KEY = st.secrets["GEMINI_KEY"]
    P_KEY = st.secrets["PUBMED_API_KEY"]
except:
    st.error("Erreur de Secrets.")
    st.stop()

TRAD = {"Gynécologie": "Gynecology", "Endocrinologie": "Endocrinology", "Médecine Générale": "General Medicine"}

st.title("🩺 Ma Veille Médicale Expert")

with st.sidebar:
    st.header("Paramètres")
    spec_fr = st.selectbox("Spécialité", list(TRAD.keys()))
    annee = st.radio("Année", ["2024", "2025"])
    nb = st.slider("Articles", 1, 10, 5)

# LE BOUTON AVEC UNE CLÉ UNIQUE POUR ÉVITER L'ERREUR DUPLICATE
if st.button(f"Lancer la recherche en {spec_fr}", key="search_btn"):
    with st.spinner("Recherche PubMed..."):
        term = TRAD[spec_fr]
        # Encodage sécurisé de la requête
        params = {"db": "pubmed", "term": f"{term} AND {annee}[dp]", "retmode": "json", "retmax": nb, "api_key": P_KEY}
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{urllib.parse.urlencode(params)}"
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                ids = data.get("esearchresult", {}).get("idlist", [])
            
            if ids:
                st.success(f"{len(ids)} articles trouvés. Analyse IA...")
                genai.configure(api_key=G_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                liens = [f"https://pubmed.ncbi.nlm.nih.gov/{i}/" for i in ids]
                prompt = f"Tu es un expert médical. Résume en français ces articles récents : {liens}"
                
                res_ia = model.generate_content(prompt)
                st.markdown(res_ia.text)
            else:
                st.warning(f"Aucun résultat pour {term} en {annee}. Essayez 'Depuis 2024'.")
        except Exception as e:
            st.error(f"Erreur technique : {e}")
