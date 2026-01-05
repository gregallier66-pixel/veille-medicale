import streamlit as st

import google.generativeai as genai

import urllib.request

import urllib.parse

import json



st.set_page_config(page_title="Veille Médicale", layout="wide")



# Récupération des secrets (configurés dans vos settings Streamlit)

try:

G_KEY = st.secrets["GEMINI_KEY"]

P_KEY = st.secrets["PUBMED_API_KEY"]

except:

st.error("Erreur de Secrets. Vérifiez les noms GEMINI_KEY et PUBMED_API_KEY.")

st.stop()



TRAD = {"Gynécologie": "Gynecology", "Endocrinologie": "Endocrinology", "Médecine Générale": "General Medicine"}



st.title("🩺 Ma Veille Médicale Expert")



with st.sidebar:

st.header("Configuration")

spec_fr = st.selectbox("Spécialité", list(TRAD.keys()))

annee = st.radio("Année", ["2024", "2025"])

nb = st.slider("Articles", 1, 10, 5)



if st.button(f"Lancer la recherche", key="unique_search_button"):

with st.spinner("Interrogation de PubMed..."):

term = TRAD[spec_fr]


# Construction correcte de l'URL (sans .fcgi qui peut causer l'erreur 404)

base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"


params = {

"db": "pubmed",

"term": f"{term} AND {annee}[pdat]", # Changé [dp] en [pdat] pour la date de publication

"retmode": "json",

"retmax": str(nb),

"api_key": P_KEY

}


# Construction de l'URL complète

url = f"{base_url}?{urllib.parse.urlencode(params)}"


# Affichage de l'URL pour débogage (vous pouvez commenter cette ligne ensuite)

with st.expander("🔍 Voir l'URL de requête"):

st.code(url)


try:

req = urllib.request.Request(

url,

headers={

'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

}

)


with urllib.request.urlopen(req, timeout=10) as response:

data = json.loads(response.read().decode())

ids = data.get("esearchresult", {}).get("idlist", [])


if ids:

st.success(f"✅ {len(ids)} articles identifiés")


# Récupération des détails des articles

with st.spinner("Récupération des résumés..."):

fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

fetch_params = {

"db": "pubmed",

"id": ",".join(ids),

"retmode": "xml",

"api_key": P_KEY

}

fetch_full_url = f"{fetch_url}?{urllib.parse.urlencode(fetch_params)}"


# Affichage des liens PubMed

st.subheader("📚 Articles trouvés")

for i, pmid in enumerate(ids, 1):

st.markdown(f"{i}. [Article PubMed {pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)")


# Analyse IA

st.subheader("🤖 Analyse par IA")

with st.spinner("Génération du résumé..."):

genai.configure(api_key=G_KEY)

model = genai.GenerativeModel('gemini-1.5-flash')


liens = [f"https://pubmed.ncbi.nlm.nih.gov/{i}/" for i in ids]

prompt = f"""Tu es un expert médical francophone.


Voici {len(ids)} articles récents en {spec_fr} publiés en {annee}.

PMIDs: {', '.join(ids)}



Rédige une synthèse structurée en français comprenant:

1. Les tendances principales observées

2. Les découvertes notables

3. Les implications cliniques potentielles



Liens des articles: {', '.join(liens)}"""


res_ia = model.generate_content(prompt)

st.markdown(res_ia.text)


else:

st.warning(f"⚠️ Aucun résultat trouvé pour {term} en {annee}.")

st.info("💡 Conseil: Essayez une autre année ou spécialité.")


except urllib.error.HTTPError as e:

st.error(f"❌ Erreur HTTP {e.code}: {e.reason}")

st.info("Vérifiez que votre clé API PubMed est valide et active.")

except urllib.error.URLError as e:

st.error(f"❌ Erreur de connexion: {e.reason}")

except json.JSONDecodeError:

st.error("❌ Erreur lors du décodage de la réponse JSON")

except Exception as e:

st.error(f"❌ Erreur technique: {type(e).__name__} - {str(e)}")
