import streamlit as st
import google.generativeai as genai
import requests
import json
from datetime import datetime, date, timedelta
import xml.etree.ElementTree as ET
from fpdf import FPDF
import io
import pypdf
from io import BytesIO
import re

# --- CONFIGURATION INITIALE ---
st.set_page_config(page_title="Veille Médicale Pro", layout="wide")

# Récupération des clés
try:
    G_KEY = st.secrets["GEMINI_KEY"]
    genai.configure(api_key=G_KEY)
except:
    st.error("⚠️ Clé GEMINI_KEY manquante dans les secrets")
    st.stop()

DEEPL_KEY = st.secrets.get("DEEPL_KEY", None)
EMAIL_USER = "gregallier66@gmail.com" # Requis pour Unpaywall

# --- DICTIONNAIRES DE RÉFÉRENCE ---
TRAD = {
    "Gynécologie": "Gynecology",
    "Obstétrique": "Obstetrics",
    "Anesthésie-Réanimation": "Anesthesiology",
    "Endocrinologie": "Endocrinology",
    "Médecine Générale": "General Medicine",
    "Chirurgie Gynécologique": "Gynecologic Surgery",
    "Infertilité": "Infertility",
    "Échographie Gynécologique": "Gynecologic Ultrasound",
    "Oncologie": "Oncology",
    "Pédiatrie": "Pediatrics"
}

TYPES_ETUDE = {
    "Tous": "",
    "Essais cliniques": "Clinical Trial",
    "Méta-analyses": "Meta-Analysis",
    "Revues systématiques": "Systematic Review",
    "Études de cohorte": "Cohort Studies"
}

JOURNAUX_SPECIALITE = {
    "Gynécologie": ["BJOG", "Obstet Gynecol", "Am J Obstet Gynecol", "Hum Reprod", "Fertil Steril"],
    "Obstétrique": ["BJOG", "Obstet Gynecol", "Am J Obstet Gynecol", "Ultrasound Obstet Gynecol"],
    "Anesthésie-Réanimation": ["Anesthesiology", "Br J Anaesth", "Anesth Analg", "Intensive Care Med"],
    "Endocrinologie": ["J Clin Endocrinol Metab", "Diabetes Care", "Eur J Endocrinol"],
    "Médecine Générale": ["BMJ", "JAMA", "N Engl J Med", "Lancet"],
    "Chirurgie Gynécologique": ["Gynecol Surg", "J Minim Invasive Gynecol"],
    "Infertilité": ["Fertil Steril", "Hum Reprod", "Reprod Biomed Online"],
    "Échographie Gynécologique": ["Ultrasound Obstet Gynecol", "J Ultrasound Med"],
    "Oncologie": ["J Clin Oncol", "Lancet Oncol", "Cancer", "JAMA Oncol"],
    "Pédiatrie": ["Pediatrics", "JAMA Pediatr", "Arch Dis Child"]
}

# --- ÉTAT DE LA SESSION ---
if 'historique' not in st.session_state: st.session_state.historique = []
if 'articles_previsualises' not in st.session_state: st.session_state.articles_previsualises = []
if 'mode_etape' not in st.session_state: st.session_state.mode_etape = 1
if 'info_recherche' not in st.session_state: st.session_state.info_recherche = {}
if 'analyses_individuelles' not in st.session_state: st.session_state.analyses_individuelles = {}

# --- FONCTIONS TECHNIQUES : ACCÈS & TRADUCTION ---

def expert_traduction(texte, mode="gemini"):
    """Traduction haute fidélité avec contexte médical expert"""
    if not texte or len(texte.strip()) < 10: return texte
    
    if mode == "deepl" and DEEPL_KEY:
        try:
            url = "https://api-free.deepl.com/v2/translate"
            data = {"auth_key": DEEPL_KEY, "text": texte[:10000], "target_lang": "FR", "source_lang": "EN", "formality": "more"}
            res = requests.post(url, data=data, timeout=20)
            return res.json()["translations"][0]["text"]
        except: pass

    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        prompt = f"""Tu es un traducteur médical expert. Traduis ce texte en français professionnel (Style Académie de Médecine).
        Conserve la précision des chiffres et des termes techniques.
        Texte : {texte[:12000]}"""
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erreur traduction: {str(e)}"

def get_pdf_via_unpaywall(pmid):
    """Récupère l'URL du PDF légal via DOI + Unpaywall"""
    try:
        # 1. Obtenir le DOI
        summary_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=json"
        res = requests.get(summary_url, timeout=10).json()
        doi = ""
        for aid in res['result'][str(pmid)].get('articleids', []):
            if aid['idtype'] == 'doi': doi = aid['value']
        
        if not doi: return None
        
        # 2. Chercher sur Unpaywall
        unpay_url = f"https://api.unpaywall.org/v2/{doi}?email={EMAIL_USER}"
        res_unpay = requests.get(unpay_url, timeout=10).json()
        if res_unpay.get('is_oa'):
            return res_unpay['best_oa_location']['url_for_pdf']
    except:
        return None
    return None

def analyser_article_complet(pmid, article_info, progress_callback):
    """Processus complet : Téléchargement -> Traduction -> Analyse"""
    pdf_url = get_pdf_via_unpaywall(pmid)
    if not pdf_url:
        return None, "PDF non trouvé en accès libre (Unpaywall)"
    
    progress_callback("📥 Téléchargement du PDF...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(pdf_url, headers=headers, timeout=30)
        with BytesIO(response.content) as f:
            reader = pypdf.PdfReader(f)
            texte_brut = ""
            for i in range(min(len(reader.pages), 12)):
                texte_brut += reader.pages[i].extract_text() + "\n"
        
        if len(texte_brut) < 200: return None, "Extraction texte échouée"
        
        progress_callback("🌐 Traduction experte...")
        texte_fr = expert_traduction(texte_brut)
        
        progress_callback("🤖 Analyse par IA...")
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        prompt = f"""Réalise une analyse médicale structurée de cet article.
        Titre : {article_info['title_fr']}
        Contenu : {texte_fr[:10000]}
        Structure : Objectif, Méthodologie, Résultats clés, Limites, Implications cliniques."""
        
        analysis = model.generate_content(prompt).text
        return {'texte_pdf': texte_fr, 'analyse': analysis}, None
        
    except Exception as e:
        return None, str(e)

# --- FONCTIONS DE RECHERCHE PUBMED ---

def traduire_mots_cles(mots_cles_fr):
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        prompt = f"Traduis ces termes médicaux en anglais pour PubMed (donne juste les termes) : {mots_cles_fr}"
        return model.generate_content(prompt).text.strip()
    except: return mots_cles_fr

def recuperer_titres_rapides(pmids, traduire_titres=True):
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", "rettype": "abstract"}
    articles_data = []
    try:
        response = requests.get(base_url, params=params, timeout=15)
        root = ET.fromstring(response.content)
        for article in root.findall('.//PubmedArticle'):
            pmid = article.find('.//PMID').text
            title_en = ''.join(article.find('.//ArticleTitle').itertext())
            journal = article.find('.//Journal/Title').text
            year = article.find('.//PubDate/Year').text if article.find('.//PubDate/Year') is not None else "N/A"
            
            title_fr = expert_traduction(title_en) if traduire_titres else title_en
            
            articles_data.append({
                'pmid': pmid, 'title': title_en, 'title_fr': title_fr,
                'journal': journal, 'year': year, 'date_pub': year
            })
    except: pass
    return articles_data

# --- INTERFACE STREAMLIT ---

st.title("🩺 Veille Médicale Professionnelle & Podcast")

tab1, tab2, tab3 = st.tabs(["🔍 Recherche & Analyse", "📚 Bibliothèque", "🎙️ Podcast AI"])

with tab1:
    if st.session_state.mode_etape == 1:
        with st.sidebar:
            st.header("⚙️ Configuration")
            mode_recherche = st.radio("Méthode", ["Spécialité", "Mots-clés"])
            spec_fr = st.selectbox("🏥 Spécialité", list(TRAD.keys())) if mode_recherche == "Spécialité" else None
            mots_cles = st.text_area("🔎 Mots-clés (FR)") if mode_recherche == "Mots-clés" else ""
            nb_max = st.slider("Nombre d'articles", 5, 50, 10)
            btn_chercher = st.button("Lancer la recherche", type="primary", use_container_width=True)

        if btn_chercher:
            term = TRAD[spec_fr] if mode_recherche == "Spécialité" else traduire_mots_cles(mots_cles)
            query = f"{term} AND (free full text[sb])" # On force le libre accès pour Unpaywall
            
            res = requests.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", 
                             params={"db":"pubmed", "term":query, "retmode":"json", "retmax":nb_max}).json()
            ids = res.get("esearchresult", {}).get("idlist", [])
            
            if ids:
                st.session_state.articles_previsualises = recuperer_titres_rapides(ids)
                st.session_state.mode_etape = 2
                st.rerun()
            else:
                st.warning("Aucun article trouvé en accès libre.")

    elif st.session_state.mode_etape == 2:
        st.header("📑 Sélection et Analyse")
        if st.button("↩️ Nouvelle recherche"):
            st.session_state.mode_etape = 1
            st.rerun()

        articles_selectionnes = []
        for i, art in enumerate(st.session_state.articles_previsualises):
            col1, col2 = st.columns([0.1, 0.9])
            if col1.checkbox("", key=f"sel_{art['pmid']}"):
                articles_selectionnes.append(art)
            col2.markdown(f"**{art['title_fr']}**\n*{art['journal']} ({art['year']})*")
        
        if st.button("🚀 ANALYSER LA SÉLECTION", type="primary") and articles_selectionnes:
            for art in articles_selectionnes:
                status = st.empty()
                res, err = analyser_article_complet(art['pmid'], art, lambda m: status.info(m))
                if res:
                    st.session_state.analyses_individuelles[art['pmid']] = {**art, **res}
                    st.success(f"Analysé : {art['pmid']}")
                else:
                    st.error(f"Échec {art['pmid']} : {err}")
            st.balloons()

with tab3:
    st.header("🎙️ Briefing Audio (Style Podcast)")
    if not st.session_state.analyses_individuelles:
        st.info("Analysez d'abord des articles dans l'onglet Recherche.")
    else:
        if st.button("✨ Générer le script du Podcast"):
            with st.spinner("Synthèse des données..."):
                all_text = "\n\n".join([f"ARTICLE {i}: {a['analyse']}" for i, a in enumerate(st.session_state.analyses_individuelles.values())])
                
                model = genai.GenerativeModel('gemini-2.0-flash-exp')
                prompt = f"""Tu es le producteur d'un podcast médical de haute volée. 
                Crée un dialogue de 5 minutes entre deux médecins, Thomas et Sophie.
                Ils discutent des articles suivants de manière dynamique, critique et pratique.
                Rends cela vivant : "Tiens Sophie, tu as vu cette étude sur...", "Oui Thomas, mais ce qui m'a surpris c'est l'échantillon...".
                CONTENU : {all_text}"""
                
                podcast_script = model.generate_content(prompt).text
                st.markdown(podcast_script)
                st.download_button("📥 Télécharger le script", podcast_script)
