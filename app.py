import streamlit as st
import google.generativeai as genai
import urllib.request
import urllib.parse
import json

# Configuration de la page
st.set_page_config(page_title="Veille Médicale Expert", layout="wide")

# 1. Récupération sécurisée des secrets
try:
    G_KEY = st.secrets["GEMINI_KEY"]
    P_KEY = st.secrets["PUBMED_API_KEY"]
except Exception as e:
    st.error("⚠️ Erreur : Clés API manquantes dans les Secrets Streamlit.")
    st.stop()

# 2. Dictionnaire de traduction
TRAD = {
    "Gynécologie": "Gynecology",
    "Endocrinologie": "Endocrinology", 
    "Médecine Générale": "General Medicine"
}

st.title("🩺 Ma Veille Médicale Expert")

# 3. Barre latérale de configuration
with st.sidebar:
    st.header("Configuration")
    spec_fr = st.selectbox("Spécialité", list(TRAD.keys()))
    annee = st.radio("Année de publication", ["2024", "2025"])
    nb_art = st.slider("Nombre d'articles à analyser", 1, 10, 5)

# 4. Logique de recherche au clic
if st.button(f"Lancer la veille en {spec_fr}", key="unique_search_button"):
    with st.spinner("Interrogation de PubMed..."):
        term_en = TRAD[spec_fr]
        
        # Préparation des paramètres de recherche
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": f"{term_en} AND {annee}[pdat]",
            "retmode": "json",
            "retmax": str(nb_art),
            "api_key": P_KEY
        }
        
        # Encodage de l'URL pour éviter l'erreur 400
        full_url = f"{base_url}?{urllib.parse.urlencode(params)}"
        
        try:
            # Envoi de la requête avec un User-Agent pour éviter les blocages
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            req = urllib.request.Request(full_url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode())
                ids = data.get("esearchresult", {}).get("idlist", [])
            
            if ids:
                st.success(f"✅ {len(ids)} articles trouvés pour {spec_fr} ({annee})")
                
                # Liens cliquables
                st.subheader("📚 Sources identifiées")
                liens_pubmed = [f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" for pmid in ids]
                for i, url in enumerate(liens_pubmed, 1):
                    st.markdown(f"{i}. [Consulter l'article sur PubMed]({url})")
                
                # 5. Analyse par l'IA Gemini
                st.divider()
                st.subheader("🤖 Synthèse de l'IA")
                with st.spinner("L'IA analyse les publications..."):
                    genai.configure(api_key=G_KEY)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    
                    prompt = f"""Tu es un expert médical francophone. 
                    Voici une liste d'articles récents en {spec_fr} ({annee}).
                    Sources : {', '.join(liens_pubmed)}
                    
                    Rédige une synthèse structurée en français comprenant :
                    1. Les thématiques majeures.
                    2. Les avancées ou points clés.
                    3. Les implications pratiques pour le clinicien."""
                    
                    try:
                        res_ia = model.generate_content(prompt)
                        st.markdown(res_ia.text)
                    except Exception as e_ia:
                        st.error(f"Erreur IA : {str(e_ia)}")
            else:
                st.warning(f"Aucun résultat trouvé pour '{term_en}' en {annee}. Essayez une autre année.")
                
        except urllib.error.HTTPError as e:
            st.error(f"Erreur PubMed {e.code}. Vérifiez votre clé API PubMed.")
        except Exception as e:
            st.error(f"Erreur technique : {str(e)}")

# Pied de page
st.caption("Données issues de PubMed via NCBI Entrez API.")
