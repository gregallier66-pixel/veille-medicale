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

st.set_page_config(page_title="Veille Médicale Pro", layout="wide")

# Récupération des clés
try:
    G_KEY = st.secrets["GEMINI_KEY"]
except:
    st.error("⚠️ Clé GEMINI_KEY manquante")
    st.stop()

DEEPL_KEY = st.secrets.get("DEEPL_KEY", None)

# Spécialités
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
    "Études de cohorte": "Cohort Studies",
    "Études cas-témoins": "Case-Control Studies"
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

SOURCES_PAR_SPECIALITE = {
    "Gynécologie": {
        "CNGOF": {"url": "http://www.cngof.fr", "description": "CNGOF", "recherche": "http://www.cngof.fr/?s="},
        "ACOG": {"url": "https://www.acog.org", "description": "ACOG", "recherche": "https://www.acog.org/search?q="}
    },
    "Obstétrique": {
        "CNGOF": {"url": "http://www.cngof.fr", "description": "CNGOF", "recherche": "http://www.cngof.fr/?s="}
    },
    "Anesthésie-Réanimation": {
        "SFAR": {"url": "https://sfar.org", "description": "SFAR", "recherche": "https://sfar.org/?s="}
    },
    "Endocrinologie": {
        "SFE": {"url": "https://www.sfendocrino.org", "description": "SFE", "recherche": "https://www.sfendocrino.org/?s="}
    },
    "Médecine Générale": {
        "HAS": {"url": "https://www.has-sante.fr", "description": "HAS", "recherche": "https://www.has-sante.fr/jcms/recherche?text="}
    },
    "Chirurgie Gynécologique": {
        "CNGOF": {"url": "http://www.cngof.fr", "description": "CNGOF", "recherche": "http://www.cngof.fr/?s="}
    },
    "Infertilité": {
        "ESHRE": {"url": "https://www.eshre.eu", "description": "ESHRE", "recherche": "https://www.eshre.eu/search?q="}
    },
    "Échographie Gynécologique": {
        "ISUOG": {"url": "https://www.isuog.org", "description": "ISUOG", "recherche": "https://www.isuog.org/search.html?q="}
    },
    "Oncologie": {
        "INCa": {"url": "https://www.e-cancer.fr", "description": "INCa", "recherche": "https://www.e-cancer.fr/Recherche?SearchText="}
    },
    "Pédiatrie": {
        "SFP": {"url": "https://www.sfpediatrie.com", "description": "SFP", "recherche": "https://www.sfpediatrie.com/?s="}
    }
}

# Session state
if 'historique' not in st.session_state:
    st.session_state.historique = []
if 'articles_previsualises' not in st.session_state:
    st.session_state.articles_previsualises = []
if 'mode_etape' not in st.session_state:
    st.session_state.mode_etape = 1
if 'info_recherche' not in st.session_state:
    st.session_state.info_recherche = {}
if 'analyses_individuelles' not in st.session_state:
    st.session_state.analyses_individuelles = {}
if 'fichiers_finaux' not in st.session_state:
    st.session_state.fichiers_finaux = {}

def traduire_avec_deepl(texte, api_key):
    """Traduit avec DeepL"""
    try:
        url = "https://api-free.deepl.com/v2/translate"
        data = {"auth_key": api_key, "text": texte, "target_lang": "FR", "source_lang": "EN", "formality": "more"}
        response = requests.post(url, data=data, timeout=30)
        if response.status_code == 200:
            return response.json()["translations"][0]["text"]
        return None
    except:
        return None

def nettoyer_titre(titre):
    """Nettoie le titre"""
    if not titre:
        return "Titre non disponible"
    titre = re.sub(r'<[^>]+>', '', titre)
    titre = re.sub(r'\s*see\s+more\s*', '', titre, flags=re.IGNORECASE)
    titre = re.sub(r'\s*\[see\s+more\]\s*', '', titre, flags=re.IGNORECASE)
    titre = re.sub(r'\s+', ' ', titre)
    return titre.strip()

def traduire_texte(texte, mode="gemini"):
    """Traduit"""
    if not texte or len(texte.strip()) < 3:
        return texte
    
    if mode == "deepl" and DEEPL_KEY:
        trad = traduire_avec_deepl(texte, DEEPL_KEY)
        if trad:
            return nettoyer_titre(trad)
    
    try:
        genai.configure(api_key=G_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        prompt = f"""Traduis en français professionnel.
Une seule traduction, sans numérotation.

{texte}"""
        
        response = model.generate_content(prompt)
        traduction = response.text.strip()
        traduction = traduction.replace("**", "").replace("Traduction:", "")
        traduction = re.sub(r'^\d+[\.\)]\s*', '', traduction)
        traduction = nettoyer_titre(traduction)
        return traduction
    except:
        return texte

def get_pdf_link_v2(pmid):
    """Récupère lien PDF"""
    try:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
        params = {"dbfrom": "pubmed", "db": "pmc", "id": pmid, "retmode": "xml", "linkname": "pubmed_pmc"}
        response = requests.get(base_url, params=params, timeout=10)
        
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            pmc_id = root.find('.//Link/Id')
            
            if pmc_id is not None:
                pmc_id_text = pmc_id.text
                urls_possibles = [
                    f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id_text}/pdf/",
                    f"https://europepmc.org/articles/PMC{pmc_id_text}?pdf=render",
                    f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id_text}/pdf/{pmc_id_text}.pdf"
                ]
                return urls_possibles, pmc_id_text
        return None, None
    except:
        return None, None

def telecharger_et_extraire_pdf(pmid, mode_traduction="gemini", progress_callback=None):
    """Télécharge et extrait PDF"""
    try:
        urls_possibles, pmc_id = get_pdf_link_v2(pmid)
        if not urls_possibles:
            return None, "PDF non disponible"
        
        if progress_callback:
            progress_callback(f"📥 Recherche PDF {pmid}...")
        
        pdf_content = None
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/pdf,text/html',
        }
        
        for url in urls_possibles:
            try:
                response = requests.get(url, timeout=30, allow_redirects=True, headers=headers)
                if response.status_code == 200 and 'application/pdf' in response.headers.get('Content-Type', ''):
                    pdf_content = response.content
                    break
            except:
                continue
        
        if not pdf_content:
            return None, f"PDF non accessible (PMC{pmc_id})"
        
        if progress_callback:
            progress_callback(f"📄 Extraction...")
        
        try:
            pdf_file = BytesIO(pdf_content)
            pdf_reader = pypdf.PdfReader(pdf_file)
            
            texte_complet = ""
            nb_pages = len(pdf_reader.pages)
            max_pages = min(nb_pages, 15)
            
            for i in range(max_pages):
                try:
                    texte_complet += pdf_reader.pages[i].extract_text() + "\n\n"
                except:
                    continue
            
            if len(texte_complet) < 100:
                return None, "Contenu insuffisant"
            
            if len(texte_complet) > 12000:
                texte_complet = texte_complet[:12000] + "\n\n[Tronqué]"
            
            if progress_callback:
                progress_callback(f"🌐 Traduction...")
            
            chunk_size = 4000
            texte_traduit = ""
            
            for i in range(0, len(texte_complet), chunk_size):
                chunk = texte_complet[i:i+chunk_size]
                texte_traduit += traduire_texte(chunk, mode=mode_traduction) + "\n\n"
            
            return texte_traduit, None
        except Exception as e:
            return None, f"Erreur extraction: {str(e)}"
    except Exception as e:
        return None, f"Erreur: {str(e)}"

def traduire_mots_cles(mots_cles_fr):
    """Traduit mots-clés"""
    try:
        genai.configure(api_key=G_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        prompt = f"""Traduis en anglais médical pour PubMed.
Uniquement les termes anglais.

{mots_cles_fr}

Anglais:"""
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return mots_cles_fr

def recuperer_titres_rapides(pmids, traduire_titres=False, mode_traduction="gemini"):
    """Récupère titres"""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", "rettype": "abstract"}
    
    try:
        response = requests.get(base_url, params=params, timeout=15)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            articles_data = []
            
            for article in root.findall('.//PubmedArticle'):
                pmid = article.find('.//PMID').text if article.find('.//PMID') is not None else "N/A"
                
                title_elem = article.find('.//ArticleTitle')
                if title_elem is not None:
                    title = ''.join(title_elem.itertext())
                else:
                    title = "Titre non disponible"
                
                title = nettoyer_titre(title)
                
                if traduire_titres and title != "Titre non disponible":
                    title_fr = traduire_texte(title, mode=mode_traduction)
                    title_fr = nettoyer_titre(title_fr)
                else:
                    title_fr = title
                
                journal_elem = article.find('.//Journal/Title')
                journal = journal_elem.text if journal_elem is not None else "Journal non disponible"
                
                year_elem = article.find('.//PubDate/Year')
                year = year_elem.text if year_elem is not None else "N/A"
                
                month_elem = article.find('.//PubDate/Month')
                month = month_elem.text if month_elem is not None else ""
                
                day_elem = article.find('.//PubDate/Day')
                day = day_elem.text if day_elem is not None else ""
                
                if month and day:
                    date_pub = f"{day}/{month}/{year}"
                elif month:
                    date_pub = f"{month} {year}"
                else:
                    date_pub = year
                
                articles_data.append({
                    'pmid': pmid,
                    'title': title,
                    'title_fr': title_fr,
                    'journal': journal,
                    'year': year,
                    'date_pub': date_pub
                })
            
            return articles_data
    except Exception as e:
        st.warning(f"Erreur: {str(e)}")
        return []
    return []

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Veille Medicale', 0, 1, 'C')
        self.ln(5)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
    
    def section_title(self, title):
        self.set_font('Arial', 'B', 14)
        self.set_fill_color(200, 220, 255)
        self.cell(0, 10, title, 0, 1, 'L', 1)
        self.ln(3)

def generer_pdf_selectionne(spec, periode, articles_selectionnes):
    """Génère PDF"""
    pdf = PDF()
    pdf.add_page()
    
    pdf.set_font('Arial', 'B', 20)
    pdf.ln(30)
    pdf.cell(0, 15, 'VEILLE MEDICALE', 0, 1, 'C')
    pdf.ln(20)
    
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, f'Specialite: {spec}', 0, 1, 'C')
    pdf.cell(0, 8, f'Periode: {periode}', 0, 1, 'C')
    pdf.cell(0, 8, f'Articles: {len(articles_selectionnes)}', 0, 1, 'C')
    pdf.cell(0, 8, f'Date: {datetime.now().strftime("%d/%m/%Y")}', 0, 1, 'C')
    
    for i, article in enumerate(articles_selectionnes, 1):
        pdf.add_page()
        pdf.section_title(f'Article {i} - PMID {article["pmid"]}')
        
        pdf.set_font('Arial', 'B', 12)
        try:
            title_clean = article['title_fr'].encode('latin-1', 'ignore').decode('latin-1')
        except:
            title_clean = article['title_fr'].encode('ascii', 'ignore').decode('ascii')
        pdf.multi_cell(0, 6, title_clean)
        pdf.ln(3)
        
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 5, f"Journal: {article['journal']} ({article['year']})", 0, 1)
        pdf.ln(3)
        
        if article.get('pdf_texte_fr'):
            try:
                pdf_clean = article['pdf_texte_fr'][:8000].encode('latin-1', 'ignore').decode('latin-1')
            except:
                pdf_clean = article['pdf_texte_fr'][:8000].encode('ascii', 'ignore').decode('ascii')
            pdf.multi_cell(0, 4, pdf_clean)
    
    pdf_output = io.BytesIO()
    pdf_string = pdf.output(dest='S').encode('latin-1')
    pdf_output.write(pdf_string)
    pdf_output.seek(0)
    
    return pdf_output.getvalue()

def generer_notebooklm_selectionne(articles_selectionnes):
    """Génère NotebookLM"""
    contenu = f"""# VEILLE MEDICALE - PODCAST
Date: {datetime.now().strftime("%d/%m/%Y")}

## ARTICLES SELECTIONNES

"""
    
    for i, article in enumerate(articles_selectionnes, 1):
        contenu += f"""
### Article {i}
Titre: {article['title_fr']}
Journal: {article['journal']} ({article['year']})
PMID: {article['pmid']}

Contenu complet:
{article.get('pdf_texte_fr', 'Non disponible')}

---
"""
    
    return contenu

# Interface
st.title("🩺 Veille Médicale Professionnelle")

if DEEPL_KEY:
    st.success("✅ DeepL Pro+ activé")
else:
    st.info("ℹ️ Traduction : Gemini 2.0 Flash")

tab1, tab2, tab3, tab4 = st.tabs(["🔍 Recherche", "📚 Historique", "🔗 Sources", "⚙️ DeepL"])

with tab1:
    # ÉTAPE 1
    if st.session_state.mode_etape == 1:
        st.header("📋 Étape 1 : Prévisualisation")
        
        with st.sidebar:
            st.header("⚙️ Paramètres")
            
            mode_recherche = st.radio("Mode", ["Par spécialité", "Par mots-clés"])
            
            if mode_recherche == "Par spécialité":
                spec_fr = st.selectbox("🏥 Spécialité", list(TRAD.keys()))
                mots_cles_custom = ""
                
                st.subheader("📰 Journaux")
                choix_journaux = st.radio("Limiter à:", ["Tous les journaux PubMed", "Journaux de la spécialité", "Un journal spécifique"])
                
                if choix_journaux == "Un journal spécifique":
                    journal_selectionne = st.selectbox("Journal:", JOURNAUX_SPECIALITE.get(spec_fr, []))
                elif choix_journaux == "Journaux de la spécialité":
                    journal_selectionne = "SPECIALITE"
                else:
                    journal_selectionne = "TOUS"
            else:
                spec_fr = None
                inclure_specialite = st.checkbox("🔬 Cibler une spécialité", value=False)
                
                if inclure_specialite:
                    spec_combo = st.selectbox("Spécialité:", list(TRAD.keys()))
                    st.subheader("📰 Journaux")
                    choix_journaux = st.radio("Limiter à:", ["Tous les journaux PubMed", "Journaux de la spécialité", "Un journal spécifique"])
                    
                    if choix_journaux == "Un journal spécifique":
                        journal_selectionne = st.selectbox("Journal:", JOURNAUX_SPECIALITE.get(spec_combo, []))
                    elif choix_journaux == "Journaux de la spécialité":
                        journal_selectionne = "SPECIALITE"
                    else:
                        journal_selectionne = "TOUS"
                else:
                    spec_combo = None
                    journal_selectionne = "TOUS"
                
                mots_cles_custom = st.text_area("🔎 Mots-clés", placeholder="Ex: hypertension gravidique", height=80)
            
            st.subheader("🎯 Zone")
            zone_recherche = st.radio("Chercher dans:", ["Titre et résumé", "Titre uniquement", "Résumé uniquement"])
            
            st.subheader("📅 Période")
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Début**")
                date_debut = st.date_input("Début", value=date(2024, 1, 1), format="DD/MM/YYYY", label_visibility="collapsed")
            with col2:
                st.write("**Fin**")
                date_fin = st.date_input("Fin", value=date.today(), format="DD/MM/YYYY", label_visibility="collapsed")
            
            st.subheader("🔬 Filtres")
            mode_contenu = st.radio("Type:", ["PDF complets uniquement", "Titre + résumé", "Titre uniquement"])
            type_etude = st.selectbox("Type d'étude", list(TYPES_ETUDE.keys()))
            nb_max = st.slider("Max résultats", 10, 200, 50, 10)
            
            mode_trad = "deepl" if DEEPL_KEY else "gemini"
            traduire_titres = st.checkbox("🌐 Traduire titres", value=True)
        
        if st.button("🔍 LANCER", type="primary", use_container_width=True):
            
            if mode_recherche == "Par spécialité":
                term = TRAD[spec_fr]
                display_term = spec_fr
                spec_utilisee = spec_fr
            else:
                if not mots_cles_custom:
                    st.error("⚠️ Entrez des mots-clés")
                    st.stop()
                
                with st.spinner("🌐 Traduction..."):
                    term = traduire_mots_cles(mots_cles_custom)
                
                display_term = f"Mots-clés: {mots_cles_custom}"
                
                if inclure_specialite and spec_combo:
                    term = f"{term} AND {TRAD[spec_combo]}"
                    spec_utilisee = spec_combo
                else:
                    spec_utilisee = "Personnalisé"
            
            query_parts = [term]
            
            if "Titre uniquement" in zone_recherche:
                query_parts[0] = f"{query_parts[0]}[Title]"
            elif "Résumé uniquement" in zone_recherche:
                query_parts[0] = f"{query_parts[0]}[Abstract]"
            
            date_debut_pubmed = date_debut.strftime("%Y/%m/%d")
            date_fin_pubmed = date_fin.strftime("%Y/%m/%d")
            query_parts.append(f"{date_debut_pubmed}:{date_fin_pubmed}[pdat]")
            
            if "PDF complets" in mode_contenu:
                query_parts.append("free full text[sb]")
            
            if journal_selectionne == "SPECIALITE":
                journaux_liste = JOURNAUX_SPECIALITE.get(spec_utilisee if mode_recherche == "Par spécialité" else spec_combo, [])
                if journaux_liste:
                    journaux_query = " OR ".join([f'"{j}"[Journal]' for j in journaux_liste])
                    query_parts.append(f"({journaux_query})")
            elif journal_selectionne != "TOUS":
                query_parts.append(f'"{journal_selectionne}"[Journal]')
            
            if TYPES_ETUDE[type_etude]:
                query_parts.append(f"{TYPES_ETUDE[type_etude]}[ptyp]")
            
            query = " AND ".join(query_parts)
            
            base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": nb_max, "sort": "date"}
            
            try:
                with st.spinner("🔎 Recherche..."):
                    response = requests.get(base_url, params=params, timeout=15)
                
                if response.status_code != 200:
                    st.error(f"❌ Erreur: {response.status_code}")
                    st.stop()
                
                data = response.json()
                ids = data.get("esearchresult", {}).get("idlist", [])
                count = data.get("esearchresult", {}).get("count", "0")
                
                if not ids:
                    st.warning(f"⚠️ Aucun article")
                    st.stop()
                
                st.success(f"✅ {count} articles - Affichage de {len(ids)}")
                
                with st.spinner("📄 Récupération..."):
                    articles_preview = recuperer_titres_rapides(ids, traduire_titres=traduire_titres, mode_traduction=mode_trad)
                
                st.session_state.articles_previsualises = articles_preview
                st.session_state.info_recherche = {
                    'display_term': display_term,
                    'periode': f"du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}",
                    'spec': spec_utilisee,
                    'mode_contenu': mode_contenu,
                    'mode_traduction': mode_trad,
                    'requete': query
                }
                
                st.session_state.mode_etape = 2
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ {str(e)}")
    
    # ÉTAPE 2
    elif st.session_state.mode_etape == 2:
        st.header("📑 Étape 2 : Sélection")
        
        if not st.session_state.articles_previsualises:
            if st.button("↩️ Retour"):
                st.session_state.mode_etape = 1
                st.rerun()
            st.stop()
        
        st.info(f"**{st.session_state.info_recherche['display_term']}** | {st.session_state.info_recherche['periode']}")
        
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("✅ Tout sélectionner"):
                for i in range(len(st.session_state.articles_previsualises)):
                    st.session_state[f"select_{i}"] = True
                st.rerun()
        
        with col_btn2:
            if st.button("↩️ Nouvelle recherche"):
                st.session_state.mode_etape = 1
                st.session_state.articles_previsualises = []
                st.session_state.analyses_individuelles = {}
                st.rerun()
        
        st.divider()
        
        articles_selectionnes = []
        
        for i, article in enumerate(st.session_state.articles_previsualises):
            col_check, col_info = st.columns([0.1, 0.9])
            
            with col_check:
                selected = st.checkbox("", key=f"select_{i}", label_visibility="collapsed")
            
            with col_info:
                st.markdown(f"**{i+1}. {article['title_fr']}**")
                st.caption(f"📰 {article['journal']} | 📅 {article['date_pub']} | PMID: [{article['pmid']}](https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/)")
            
            if selected:
                articles_selectionnes.append(article['pmid'])
            
            st.divider()
        
        st.markdown(f"**{len(articles_selectionnes)} sélectionné(s)**")
        
        if 0 < len(articles_selectionnes) <= 20:
            st.divider()
            
            if st.button("🚀 ANALYSER", type="primary", use_container_width=True):
                
                st.session_state.analyses_individuelles = {}
                mode_trad = st.session_state.info_recherche.get('mode_traduction', 'gemini')
                
                for idx, pmid in enumerate(articles_selectionnes):
                    st.subheader(f"📄 Article {idx+1}/{len(articles_selectionnes)} - PMID {pmid}")
                    
                    article_info = next((a for a in st.session_state.articles_previsualises if a['pmid'] == pmid), None)
                    
                    if not article_info:
                        continue
                    
                    st.markdown(f"**{article_info['title_fr']}**")
                    
                    status_box = st.empty()
                    
                    def callback(msg):
                        status_box.info(msg)
                    
                    pdf_texte_fr, erreur = telecharger_et_extraire_pdf(pmid, mode_traduction=mode_trad, progress_callback=callback)
                    
                    status_box.empty()
                    
                    if pdf_texte_fr:
                        st.success(f"✅ PDF extrait et traduit ({len(pdf_texte_fr)} caractères)")
                        
                        with st.expander("📄 Lire le PDF"):
                            st.text_area("Contenu:", pdf_texte_fr, height=400, key=f"pdf_{pmid}")
                        
                        with st.spinner("🤖 Analyse IA..."):
                            try:
                                genai.configure(api_key=G_KEY)
                                model = genai.GenerativeModel('gemini-2.0-flash-exp')
                                
                                prompt = f"""Analyse médicale.

Titre: {article_info['title_fr']}
Journal: {article_info['journal']} ({article_info['year']})

Contenu:
{pdf_texte_fr}

Analyse:

## Objectif
## Méthodologie
## Résultats
## Implications
## Limites
## Conclusion"""
                                
                                response = model.generate_content(prompt)
                                analyse = response.text
                                
                                st.markdown("### 🤖 Analyse IA")
                                st.markdown(analyse)
                                
                                st.session_state.analyses_individuelles[pmid] = {
                                    'pmid': pmid,
                                    'title': article_info['title'],
                                    'title_fr': article_info['title_fr'],
                                    'journal': article_info['journal'],
                                    'year': article_info['year'],
                                    'date_pub': article_info['date_pub'],
                                    'pdf_texte_fr': pdf_texte_fr,
                                    'analyse_ia': analyse
                                }
                            except Exception as e:
                                st.error(f"❌ Erreur: {str(e)}")
                    else:
                        st.error(f"❌ {erreur}")
                    
                    st.divider()
                
                # PASSER À ÉTAPE 3
                if st.session_state.analyses_individuelles:
                    st.session_state.mode_etape = 3
                    st.rerun()
    
    # ÉTAPE 3 : SÉLECTION FINALE
    elif st.session_state.mode_etape == 3:
        st.header("📚 Étape 3 : Sélection finale")
        
        st.info("Sélectionnez les articles à inclure dans le PDF et le podcast")
        
        articles_finaux_ids = []
        
        for pmid, data in st.session_state.analyses_individuelles.items():
            col_check, col_info = st.columns([0.1, 0.9])
            
            with col_check:
                include = st.checkbox("", key=f"final_{pmid}", value=True, label_visibility="collapsed")
            
            with col_info:
                st.markdown(f"**{data['title_fr']}**")
                st.caption(f"{data['journal']} | {data['date_pub']}")
                
                # AFFICHER L'ANALYSE ICI
                with st.expander("🤖 Voir l'analyse IA"):
                    st.markdown(data['analyse_ia'])
            
            if include:
                articles_finaux_ids.append(pmid)
            
            st.divider()
        
        if articles_finaux_ids:
            st.success(f"✅ {len(articles_finaux_ids)} article(s) sélectionné(s)")
            
            if st.button("📦 GÉNÉRER LES FICHIERS", type="primary", use_container_width=True):
                
                articles_finaux = [st.session_state.analyses_individuelles[pmid] for pmid in articles_finaux_ids]
                
                with st.spinner("📦 Génération des fichiers..."):
                    pdf_final = generer_pdf_selectionne(
                        st.session_state.info_recherche['spec'],
                        st.session_state.info_recherche['periode'],
                        articles_finaux
                    )
                    
                    notebooklm = generer_notebooklm_selectionne(articles_finaux)
                
                # SAUVEGARDER dans session_state
                st.session_state.fichiers_finaux = {
                    'pdf': pdf_final,
                    'notebooklm': notebooklm,
                    'articles': articles_finaux
                }
                
                # PASSER À ÉTAPE 4
                st.session_state.mode_etape = 4
                st.rerun()
    
    # ÉTAPE 4 : TÉLÉCHARGEMENTS
    elif st.session_state.mode_etape == 4:
        st.header("🎉 Veille terminée !")
        
        st.success(f"✅ {len(st.session_state.fichiers_finaux['articles'])} article(s) analysé(s)")
        
        # RÉCAPITULATIF
        st.subheader("📋 Récapitulatif")
        for i, article in enumerate(st.session_state.fichiers_finaux['articles'], 1):
            with st.expander(f"📄 Article {i} - {article['title_fr'][:80]}..."):
                st.markdown(f"**Journal:** {article['journal']} ({article['year']})")
                st.markdown(f"**PMID:** [{article['pmid']}](https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/)")
                st.markdown("### 🤖 Analyse IA")
                st.markdown(article['analyse_ia'])
        
        st.divider()
        
        # TÉLÉCHARGEMENTS
        st.subheader("📥 Téléchargements")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.download_button(
                "📄 PDF Final",
                st.session_state.fichiers_finaux['pdf'],
                f"veille_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        
        with col2:
            st.download_button(
                "🎙️ Fichier NotebookLM",
                st.session_state.fichiers_finaux['notebooklm'],
                f"podcast_{datetime.now().strftime('%Y%m%d')}.txt",
                use_container_width=True,
                help="Téléchargez ce fichier puis importez-le sur NotebookLM"
            )
        
        st.divider()
        
        # GUIDE NOTEBOOKLM
        st.subheader("🎙️ Créer votre podcast avec NotebookLM")
        
        st.markdown("""
### 📝 Instructions :

1. **Téléchargez** le fichier NotebookLM ci-dessus (clic sur le bouton bleu)

2. **Allez sur** https://notebooklm.google.com

3. **Créez un nouveau notebook** (bouton "+ New notebook")

4. **Importez le fichier** :
   - Cliquez sur "Sources" → "Upload"
   - Sélectionnez le fichier `.txt` téléchargé
   - Attendez l'import (quelques secondes)

5. **Générez le podcast** :
   - Cliquez sur l'onglet "Notebook guide" en bas
   - Cliquez sur "Generate" (ou "Audio overview")
   - Attendez 2-5 minutes ⏳

6. **Écoutez et téléchargez** :
   - Le podcast apparaît dans le player audio
   - Cliquez sur "⋮" → "Download" pour le télécharger en MP3

### ✨ Résultat :
Un podcast professionnel de **10-20 minutes** avec 2 voix IA discutant de vos articles médicaux en anglais !

**Gratuit et illimité** 🎉
        """)
        
        st.link_button("🔗 Ouvrir NotebookLM", "https://notebooklm.google.com", use_container_width=True)
        
        st.divider()
        
        if st.button("🔄 Nouvelle recherche", use_container_width=True):
            st.session_state.mode_etape = 1
            st.session_state.articles_previsualises = []
            st.session_state.analyses_individuelles = {}
            st.session_state.fichiers_finaux = {}
            st.rerun()

with tab2:
    st.header("📚 Historique")

with tab3:
    st.header("🔗 Sources")
    
    spec_src = st.selectbox("Spécialité:", list(SOURCES_PAR_SPECIALITE.keys()))
    
    if spec_src:
        for nom, info in SOURCES_PAR_SPECIALITE[spec_src].items():
            with st.expander(f"📚 {nom}"):
                st.markdown(f"**{info['description']}**")
                mots_cles = st.text_input("Rechercher:", key=f"src_{nom}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if mots_cles:
                        st.link_button("🔍 Rechercher", f"{info['recherche']}{mots_cles}")
                with col2:
                    st.link_button("🏠 Accueil", info['url'])

with tab4:
    st.header("⚙️ DeepL")
    
    st.markdown("""
## DeepL Pro+

1. https://www.deepl.com/pro#developer
2. API Pro+ (29,99€/mois)
3. Settings → Secrets → DEEPL_KEY

Résiliation: Account → Cancel
    """)

st.markdown("---")
st.caption("💊 Veille médicale | Gemini 2.0 Flash")
