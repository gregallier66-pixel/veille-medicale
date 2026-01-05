import streamlit as st
import google.generativeai as genai
import urllib.request
import urllib.parse
import json

# Configuration de la page
st.set_page_config(page_title="Ma Veille Médicale", layout="wide")

# 1. Vérification des Secrets
try:
    G_KEY = st.secrets["GEMINI_KEY"]
    P_KEY = st.secrets["PUBMED_API_KEY"]
except Exception as e:
    st.error("ERREUR : Les secrets GEMINI_KEY ou PUBMED_API_KEY sont absents.")
    st.stop()

# 2. Dictionnaire de traduction (Anglais pour PubMed)
TRAD = {
    "Gynécologie": "Gynecology",
    "Endocrinologie": "Endocrinology", 
    "Médecine Générale": "General Medicine"
}

st.title("🩺 Ma Veille Médicale Expert")

# 3. Paramètres dans la barre latérale
with st.sidebar:
    st.header("Paramètres")
    spec_fr = st.selectbox("Spécialité", list(TRAD.keys()))
    annee = st.radio("Année", ["2024", "2025"])
    nb_art = st.slider("Articles à analyser", 1, 5, 2)

# 4. Lancement de la recherche
# Note: 'key' évite l'erreur StreamlitDuplicateElementId
if st.button(f"Lancer la recherche en {spec_fr}", key="btn_veille_unique"):
    status = st.empty()
    status.info("🔍 1. Recherche sur PubMed en cours...")
    
    term_en = TRAD[spec_fr]
    
    # Encodage sécurisé de l'URL pour éviter l'HTTP Error 400
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": f"{term_en} AND {annee}[pdat]",
        "retmode": "json",
        "retmax": str(nb_art),
        "api_key": P_KEY
    }
    full_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    
    try:
        # Requête avec User-Agent pour éviter les blocages serveurs
        req = urllib.request.Request(full_url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
            ids = data.get("esearchresult", {}).get("idlist", [])
        
        if ids:
            status.info(f"🧬 2. {len(ids)} articles trouvés. Analyse IA...")
            
            # Liens PubMed pour l'utilisateur et l'IA
            liens = [f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" for pmid in ids]
            
            # Configuration Gemini
            genai.configure(api_key=G_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"""Tu es un expert médical. 
            Résume de façon synthétique et structurée en français les articles suivants :
            {', '.join(liens)}"""
            
            resultat_ia = model.generate_content(prompt)
            
            # Affichage final
            status.empty()
            st.success("✅ Analyse terminée")
            st.markdown("### Synthèse des articles identifiés")
            st.markdown(resultat_ia.text)
            
            with st.expander("Voir les sources PubMed"):
                for l in liens:
                    st.write(l)
        else:
            status.warning(f"Aucun article trouvé pour {term_en} en {annee}.")
            
    except Exception as e:
        status.empty()
        st.error(f"Erreur technique : {e}")
