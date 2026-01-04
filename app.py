import streamlit as st
import requests
import google.generativeai as genai
import os

# Configuration de l'interface
st.set_page_config(page_title="Veille Médicale Expert", page_icon="🩺", layout="wide")

# Récupération des secrets (Configurés dans Streamlit Cloud)
GEMINI_KEY = st.secrets.get("AIzaSyCMPYJIHZ83uVhYwV6eqKxsC1pv7Hbol6g", "")
PUBMED_API_KEY = st.secrets.get("17626ab73380b71515000371bdcee0c26308", "")

# Style personnalisé
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { 
        width: 100%; 
        border-radius: 5px; 
        height: 3em; 
        background-color: #007bff; 
        color: white; 
    }
    </style>
    """, unsafe_allow_html=True)


st.title("🩺 Ma Veille Médicale Interactive")
st.write("Consultez les dernières publications PubMed analysées par l'IA.")

# Barre latérale : Choix de la spécialité
with st.sidebar:
    st.header("Filtres de recherche")
    specialite = st.selectbox(
        "Choisissez une spécialité :",
        ["Gynécologie-Obstétrique", "Endocrinologie", "Médecine Générale"]
    )
    
    periode = st.radio("Période :", ["Dernières 24h", "Depuis 2024", "Depuis 2025"])
    nb_resultats = st.slider("Nombre d'articles à analyser", 1, 10, 5)

# Construction de la requête PubMed selon le choix
queries = {
    "Gynécologie-Obstétrique": "(gynecology[Title] OR obstetrics[Title])",
    "Endocrinologie": "endocrinology[Title]",
    "Médecine Générale": "'general medicine'[Title]"
}

date_filter = "2024:2026[Date - Publication]" if periode == "Depuis 2024" else "2025:2026[Date - Publication]"
if periode == "Dernières 24h":
    date_filter = "1[Relative Date]" # Articles du dernier jour

final_query = f"{queries[specialite]} AND {date_filter}"

# Fonction de recherche
def fetch_pubmed(query, count):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed", "term": query, "retmode": "json", 
        "retmax": count, "api_key": PUBMED_API_KEY
    }
    try:
        res = requests.get(url, params=params).json()
        return res.get("esearchresult", {}).get("idlist", [])
    except:
        return []

# Bouton d'action
if st.button(f"Analyser les nouveautés en {specialite}"):
    if not GEMINI_KEY:
        st.error("Clé API Gemini manquante dans les Secrets.")
    else:
        with st.spinner(f"Analyse des articles de {specialite} en cours..."):
            ids = fetch_pubmed(final_query, nb_resultats)
            
            if ids:
                # Configuration Gemini
                genai.configure(api_key=GEMINI_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                liens = [f"https://pubmed.ncbi.nlm.nih.gov/{i}/" for i in ids]
                
                prompt = f"""
                Tu es un assistant médical pour un spécialiste en {specialite}. 
                Voici des liens PubMed : {liens}.
                Pour chaque article :
                1. Donne le titre en Français.
                2. Fais un résumé pédagogique (3 phrases max).
                3. Explique l'intérêt pratique pour un médecin.
                Utilise un ton professionnel et structure avec des titres.
                """
                
                response = model.generate_content(prompt)
                
                st.success("Analyse terminée !")
                st.markdown(response.text)
                
                with st.expander("Voir les sources originales"):
                    for l in liens:
                        st.write(l)
            else:
                st.warning("Aucun article trouvé pour ces critères.")
