import streamlit as st
import google.generativeai as genai
import requests

st.set_page_config(page_title="Veille Médicale", layout="wide")

# Vérification des secrets (nécessaire pour le fonctionnement)
try:
    G_KEY = st.secrets["GEMINI_KEY"]
    P_KEY = st.secrets["PUBMED_API_KEY"]
except:
    st.error("Erreur de Secrets.")
    st.stop()

# Dictionnaire anglais pour PubMed
TRADUCTION = {
    "Gynécologie": "Gynecology",
    "Endocrinologie": "Endocrinology",
    "Médecine Générale": "General Medicine"
}

st.title("🩺 Ma Veille Médicale Expert")

with st.sidebar:
    st.header("Configuration")
    spec_fr = st.selectbox("Spécialité", list(TRADUCTION.keys()))
    # On simplifie la période pour maximiser les chances de résultats
    periode = st.radio("Période", ["Depuis 2024", "Depuis 2025"])
    nb_art = st.slider("Nombre d'articles", 1, 10, 5)

if st.button(f"Lancer la veille en {spec_fr}"):
    with st.spinner("Recherche sur PubMed..."):
        term_en = TRADUCTION[spec_fr]
        annee = "2024" if periode == "Depuis 2024" else "2025"
        
        # Requête simplifiée au maximum : Terme + Année
        query = f"{term_en} AND {annee}[DP]"
        
        u = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": nb_art,
            "api_key": P_KEY
        }
        
        try:
            r = requests.get(u, params=params).json()
            ids = r.get("esearchresult", {}).get("idlist", [])
            
            if ids:
                st.success(f"Trouvé : {len(ids)} articles. Analyse IA en cours...")
                
                # Configuration de l'IA Gemini
                genai.configure(api_key=G_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # Création des liens PubMed
                links = [f"https://pubmed.ncbi.nlm.nih.gov/{i}/" for i in ids]
                
                # Prompt pour l'IA
                prompt = f"Tu es un expert médical. Voici des liens d'articles récents : {links}. Fais une synthèse structurée en français pour chaque article."
                
                response = model.generate_content(prompt)
                st.markdown(response.text)
            else:
                # Message si vraiment rien n'est trouvé
                st.warning(f"PubMed ne renvoie aucun résultat pour '{term_en}' en {annee}. Vérifiez la connexion PubMed.")
        except Exception as e:
            st.error(f"Erreur technique : {e}")
