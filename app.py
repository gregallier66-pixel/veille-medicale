import streamlit as st
import google.generativeai as genai
import requests
from datetime import datetime, date
import xml.etree.ElementTree as ET
from fpdf import FPDF
import io
import pypdf
from io import BytesIO

st.set_page_config(page_title="Veille Médicale Pro", layout="wide")

try:
    G_KEY = st.secrets["GEMINI_KEY"]
except:
    st.error("⚠️ Clé GEMINI_KEY manquante")
    st.stop()

DEEPL_KEY = st.secrets.get("DEEPL_KEY", None)

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
    "Revues systématiques": "Systematic Review"
}

JOURNAUX_SPECIALITE = {
    "Gynécologie": ["BJOG", "Obstet Gynecol", "Am J Obstet Gynecol"],
    "Obstétrique": ["BJOG", "Obstet Gynecol", "Am J Obstet Gynecol"],
    "Anesthésie-Réanimation": ["Anesthesiology", "Br J Anaesth", "Anesth Analg"],
    "Endocrinologie": ["J Clin Endocrinol Metab", "Diabetes Care"],
    "Médecine Générale": ["BMJ", "JAMA", "N Engl J Med", "Lancet"],
    "Oncologie": ["J Clin Oncol", "Lancet Oncol", "Cancer"],
    "Pédiatrie": ["Pediatrics", "JAMA Pediatr"]
}

if 'historique' not in st.session_state:
    st.session_state.historique = []

def traduire_avec_deepl(texte, api_key):
    try:
        url = "https://api-free.deepl.com/v2/translate"
        data = {"auth_key": api_key, "text": texte, "target_lang": "FR", "source_lang": "EN"}
        response = requests.post(url, data=data, timeout=30)
        if response.status_code == 200:
            return response.json()["translations"][0]["text"]
        return None
    except:
        return None

def traduire_texte(texte, mode="gemini"):
    if mode == "deepl" and DEEPL_KEY:
        trad = traduire_avec_deepl(texte, DEEPL_KEY)
        if trad:
            return trad
    
    try:
        genai.configure(api_key=G_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(f"Traduis en français: {texte}")
        return response.text.strip()
    except:
        return texte

def get_pdf_link(pmid):
    try:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
        params = {"dbfrom": "pubmed", "db": "pmc", "id": pmid, "retmode": "xml"}
        response = requests.get(base_url, params=params, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            pmc_id = root.find('.//Link/Id')
            if pmc_id is not None:
                return f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id.text}/pdf/", pmc_id.text
        return None, None
    except:
        return None, None

def telecharger_et_extraire_pdf(pmid, mode_traduction="gemini"):
    try:
        pdf_url, pmc_id = get_pdf_link(pmid)
        if not pdf_url:
            return None, "PDF non disponible"
        
        response = requests.get(pdf_url, timeout=30)
        if response.status_code != 200:
            return None, f"Erreur {response.status_code}"
        
        try:
            pdf_file = BytesIO(response.content)
            pdf_reader = pypdf.PdfReader(pdf_file)
            
            texte = ""
            for i in range(min(len(pdf_reader.pages), 10)):
                texte += pdf_reader.pages[i].extract_text() + "\n\n"
            
            if len(texte) > 8000:
                texte = texte[:8000]
            
            texte_traduit = traduire_texte(texte, mode=mode_traduction)
            
            return texte_traduit, None
        except Exception as e:
            return None, f"Erreur extraction: {str(e)}"
    except Exception as e:
        return None, f"Erreur: {str(e)}"

st.title("🩺 Veille Médicale Professionnelle")

if DEEPL_KEY:
    st.success("✅ DeepL Pro+ activé")
else:
    st.info("ℹ️ Gemini 2.0 Flash")

with st.sidebar:
    st.header("⚙️ Paramètres")
    
    mode = st.radio("Mode", ["Par spécialité", "Par mots-clés"])
    
    if mode == "Par spécialité":
        spec = st.selectbox("Spécialité", list(TRAD.keys()))
        mots = ""
        
        journaux = ["Tous"] + JOURNAUX_SPECIALITE.get(spec, [])
        journal = st.selectbox("Journal", journaux)
    else:
        spec = None
        journal = "Tous"
        mots = st.text_area("Mots-clés", height=80)
    
    st.subheader("📅 Période")
    col1, col2 = st.columns(2)
    with col1:
        d1 = st.date_input("Début", value=date(2024, 1, 1), format="DD/MM/YYYY")
    with col2:
        d2 = st.date_input("Fin", value=date.today(), format="DD/MM/YYYY")
    
    pdf_only = st.checkbox("PDF uniquement", value=True)
    type_e = st.selectbox("Type", list(TYPES_ETUDE.keys()))
    nb = st.slider("Max", 10, 100, 20, 10)

if st.button("🔍 LANCER", type="primary", use_container_width=True):
    
    if mode == "Par spécialité":
        term = TRAD[spec]
        display = spec
    else:
        if not mots:
            st.error("⚠️ Entrez mots-clés")
            st.stop()
        
        genai.configure(api_key=G_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        term = model.generate_content(f"Traduis en anglais médical: {mots}").text.strip()
        display = f"Mots: {mots}"
    
    query_parts = [term]
    query_parts.append(f"{d1.strftime('%Y/%m/%d')}:{d2.strftime('%Y/%m/%d')}[pdat]")
    
    if pdf_only:
        query_parts.append("free full text[sb]")
    
    if journal != "Tous":
        query_parts.append(f'"{journal}"[Journal]')
    
    if TYPES_ETUDE[type_e]:
        query_parts.append(f"{TYPES_ETUDE[type_e]}[ptyp]")
    
    query = " AND ".join(query_parts)
    
    try:
        with st.spinner("Recherche..."):
            r = requests.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                params={"db": "pubmed", "term": query, "retmode": "json", "retmax": nb},
                timeout=15
            )
        
        if r.status_code != 200:
            st.error(f"Erreur: {r.status_code}")
            st.stop()
        
        data = r.json()
        ids = data.get("esearchresult", {}).get("idlist", [])
        count = data.get("esearchresult", {}).get("count", "0")
        
        if not ids:
            st.warning("Aucun résultat")
            st.stop()
        
        st.success(f"✅ {count} articles - {len(ids)} affichés")
        
        st.subheader("📄 Articles avec PDF")
        
        mode_trad = "deepl" if DEEPL_KEY else "gemini"
        
        for idx, pmid in enumerate(ids, 1):
            st.markdown(f"**Article {idx} - PMID {pmid}**")
            
            with st.spinner(f"Extraction PDF {idx}/{len(ids)}..."):
                pdf_texte, erreur = telecharger_et_extraire_pdf(pmid, mode_traduction=mode_trad)
            
            if pdf_texte:
                st.success("✅ PDF extrait et traduit")
                with st.expander("Lire PDF"):
                    st.text_area("", pdf_texte, height=400, key=f"pdf_{pmid}")
            else:
                st.error(f"❌ {erreur}")
            
            st.divider()
        
    except Exception as e:
        st.error(f"Erreur: {str(e)}")

st.caption("💊 Veille médicale | Gemini/DeepL")
