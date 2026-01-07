import streamlit as st
import google.generativeai as genai
import requests
from datetime import datetime, date
import xml.etree.ElementTree as ET
from fpdf import FPDF
import io
import pypdf
from io import BytesIO
import re
import time

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
    "Revues systématiques": "Systematic Review",
    "Études de cohorte": "Cohort Studies",
    "Études cas-témoins": "Case-Control Studies"
}

JOURNAUX_SPECIALITE = {
    "Gynécologie": ["BJOG", "Obstet Gynecol", "Am J Obstet Gynecol", "Hum Reprod", "Fertil Steril"],
    "Obstétrique": ["BJOG", "Obstet Gynecol", "Am J Obstet Gynecol", "Ultrasound Obstet Gynecol"],
    "Anesthésie-Réanimation": ["Anesthesiology", "Br J Anaesth", "Anesth Analg"],
    "Endocrinologie": ["J Clin Endocrinol Metab", "Diabetes Care", "Eur J Endocrinol"],
    "Médecine Générale": ["BMJ", "JAMA", "N Engl J Med", "Lancet"],
    "Chirurgie Gynécologique": ["Gynecol Surg", "J Minim Invasive Gynecol"],
    "Infertilité": ["Fertil Steril", "Hum Reprod"],
    "Échographie Gynécologique": ["Ultrasound Obstet Gynecol", "J Ultrasound Med"],
    "Oncologie": ["J Clin Oncol", "Lancet Oncol", "Cancer"],
    "Pédiatrie": ["Pediatrics", "JAMA Pediatr"]
}

SOURCES_PAR_SPECIALITE = {
    "Gynécologie": {
        "CNGOF": {"url": "http://www.cngof.fr", "description": "Collège National des Gynécologues Obstétriciens Français", "recherche": "http://www.cngof.fr/?s="},
        "ACOG": {"url": "https://www.acog.org", "description": "American College of Obstetricians and Gynecologists", "recherche": "https://www.acog.org/search?q="},
        "RCOG": {"url": "https://www.rcog.org.uk", "description": "Royal College UK", "recherche": "https://www.rcog.org.uk/search?q="},
        "HAS": {"url": "https://www.has-sante.fr", "description": "Haute Autorité de Santé", "recherche": "https://www.has-sante.fr/jcms/recherche?text="},
        "SOGC": {"url": "https://www.sogc.org", "description": "Society of Obstetricians Canada", "recherche": "https://www.sogc.org/en/content/search.aspx?q="}
    },
    "Obstétrique": {
        "CNGOF": {"url": "http://www.cngof.fr", "description": "CNGOF Obstétrique", "recherche": "http://www.cngof.fr/?s="},
        "ACOG": {"url": "https://www.acog.org", "description": "ACOG", "recherche": "https://www.acog.org/search?q="},
        "WHO": {"url": "https://www.who.int/health-topics/maternal-health", "description": "OMS Santé maternelle", "recherche": "https://www.who.int/search?query="}
    },
    "Anesthésie-Réanimation": {
        "SFAR": {"url": "https://sfar.org", "description": "Société Française Anesthésie Réanimation", "recherche": "https://sfar.org/?s="},
        "ASA": {"url": "https://www.asahq.org", "description": "American Society of Anesthesiologists", "recherche": "https://www.asahq.org/search?q="},
        "ESA": {"url": "https://www.esaic.org", "description": "European Society Anaesthesiology", "recherche": "https://www.esaic.org/search?q="}
    },
    "Endocrinologie": {
        "SFE": {"url": "https://www.sfendocrino.org", "description": "Société Française Endocrinologie", "recherche": "https://www.sfendocrino.org/?s="},
        "ADA": {"url": "https://diabetes.org", "description": "American Diabetes Association", "recherche": "https://diabetes.org/search?q="},
        "EASD": {"url": "https://www.easd.org", "description": "European Association Diabetes", "recherche": "https://www.easd.org/search?q="}
    },
    "Médecine Générale": {
        "HAS": {"url": "https://www.has-sante.fr", "description": "HAS", "recherche": "https://www.has-sante.fr/jcms/recherche?text="},
        "CNGE": {"url": "https://www.cnge.fr", "description": "Collège National Généralistes", "recherche": "https://www.cnge.fr/?s="},
        "NICE": {"url": "https://www.nice.org.uk", "description": "NICE UK", "recherche": "https://www.nice.org.uk/search?q="}
    },
    "Chirurgie Gynécologique": {
        "CNGOF": {"url": "http://www.cngof.fr", "description": "CNGOF Chirurgie", "recherche": "http://www.cngof.fr/?s="},
        "AAGL": {"url": "https://www.aagl.org", "description": "Association Gynecologic Laparoscopy", "recherche": "https://www.aagl.org/search?q="}
    },
    "Infertilité": {
        "ESHRE": {"url": "https://www.eshre.eu", "description": "European Society Human Reproduction", "recherche": "https://www.eshre.eu/search?q="},
        "ASRM": {"url": "https://www.asrm.org", "description": "American Society Reproductive Medicine", "recherche": "https://www.asrm.org/search?q="}
    },
    "Échographie Gynécologique": {
        "ISUOG": {"url": "https://www.isuog.org", "description": "International Society Ultrasound", "recherche": "https://www.isuog.org/search.html?q="},
        "CFEF": {"url": "http://www.cfef.org", "description": "Collège Français Échographie Fœtale", "recherche": "http://www.cfef.org/?s="}
    },
    "Oncologie": {
        "INCa": {"url": "https://www.e-cancer.fr", "description": "Institut National Cancer", "recherche": "https://www.e-cancer.fr/Recherche?SearchText="},
        "NCCN": {"url": "https://www.nccn.org", "description": "National Comprehensive Cancer Network", "recherche": "https://www.nccn.org/search?q="},
        "ESMO": {"url": "https://www.esmo.org", "description": "European Society Medical Oncology", "recherche": "https://www.esmo.org/search?q="}
    },
    "Pédiatrie": {
        "SFP": {"url": "https://www.sfpediatrie.com", "description": "Société Française Pédiatrie", "recherche": "https://www.sfpediatrie.com/?s="},
        "AAP": {"url": "https://www.aap.org", "description": "American Academy Pediatrics", "recherche": "https://www.aap.org/search?q="}
    }
}

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

def nettoyer_titre_complet(titre):
    if not titre:
        return "Titre non disponible"
    titre = re.sub(r'<[^>]+>', '', titre)
    titre = re.sub(r'see\s+more', '', titre, flags=re.IGNORECASE)
    titre = re.sub(r'\[see\s+more\]', '', titre, flags=re.IGNORECASE)
    titre = re.sub(r'\s+', ' ', titre)
    return titre.strip()

def traduire_texte(texte, mode="gemini"):
    if not texte or len(texte.strip()) < 3:
        return texte
    
    try:
        genai.configure(api_key=G_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        prompt = f"""Traduis en français. UNE SEULE traduction.

{texte}"""
        
        response = model.generate_content(prompt)
        traduction = response.text.strip()
        traduction = traduction.replace("**", "").replace("Traduction:", "")
        traduction = re.sub(r'^\d+[\.\)]\s*', '', traduction)
        return nettoyer_titre_complet(traduction)
    except:
        return texte

def get_pdf_link_ameliore(pmid):
    try:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
        params = {"dbfrom": "pubmed", "db": "pmc", "id": pmid, "retmode": "xml"}
        response = requests.get(base_url, params=params, timeout=10)
        
        urls = []
        pmc_id = None
        
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            pmc_elem = root.find('.//Link/Id')
            if pmc_elem is not None:
                pmc_id = pmc_elem.text
                urls.extend([
                    f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/",
                    f"https://europepmc.org/articles/PMC{pmc_id}?pdf=render"
                ])
        return urls, pmc_id
    except:
        return None, None

def telecharger_et_extraire_pdf(pmid, mode_traduction="gemini", progress_callback=None):
    try:
        urls, pmc_id = get_pdf_link_ameliore(pmid)
        if not urls:
            return None, "PDF non disponible"
        
        if progress_callback:
            progress_callback(f"📥 Téléchargement {pmid}...")
        
        pdf_content = None
        headers_list = [
            {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0', 'Accept': 'application/pdf'},
            {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)', 'Accept': 'application/pdf'}
        ]
        
        for url in urls:
            for headers in headers_list:
                try:
                    resp = requests.get(url, timeout=30, allow_redirects=True, headers=headers)
                    if resp.status_code == 200 and (b'%PDF' in resp.content[:4] or 'pdf' in resp.headers.get('Content-Type', '')):
                        pdf_content = resp.content
                        break
                except:
                    continue
            if pdf_content:
                break
            time.sleep(0.5)
        
        if not pdf_content:
            return None, f"PDF non accessible"
        
        if progress_callback:
            progress_callback("📄 Extraction...")
        
        try:
            pdf_file = BytesIO(pdf_content)
            pdf_reader = pypdf.PdfReader(pdf_file)
            texte = ""
            for i in range(min(len(pdf_reader.pages), 15)):
                try:
                    texte += pdf_reader.pages[i].extract_text() + "\n\n"
                except:
                    continue
            
            if len(texte) < 100:
                return None, "Contenu insuffisant"
            
            if len(texte) > 12000:
                texte = texte[:12000]
            
            if progress_callback:
                progress_callback("🌐 Traduction...")
            
            texte_trad = ""
            for i in range(0, len(texte), 4000):
                texte_trad += traduire_texte(texte[i:i+4000], mode=mode_traduction) + "\n\n"
            
            return texte_trad, None
        except Exception as e:
            return None, f"Erreur: {str(e)}"
    except:
        return None, "Erreur"

def traduire_mots_cles(mots):
    try:
        genai.configure(api_key=G_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(f"Traduis en anglais médical: {mots}")
        return response.text.strip()
    except:
        return mots

def recuperer_titres_rapides(pmids, traduire_titres=False, mode_traduction="gemini"):
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"}
    
    try:
        response = requests.get(base_url, params=params, timeout=15)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            articles = []
            
            for article in root.findall('.//PubmedArticle'):
                pmid = article.find('.//PMID').text if article.find('.//PMID') is not None else "N/A"
                
                title_elem = article.find('.//ArticleTitle')
                title = ''.join(title_elem.itertext()) if title_elem is not None else "Titre non disponible"
                title = nettoyer_titre_complet(title)
                
                if traduire_titres and title != "Titre non disponible":
                    title_fr = traduire_texte(title, mode=mode_traduction)
                    title_fr = nettoyer_titre_complet(title_fr)
                else:
                    title_fr = title
                
                journal_elem = article.find('.//Journal/Title')
                journal = journal_elem.text if journal_elem is not None else "N/A"
                
                year = article.find('.//PubDate/Year')
                year = year.text if year is not None else "N/A"
                
                articles.append({
                    'pmid': pmid,
                    'title': title,
                    'title_fr': title_fr,
                    'journal': journal,
                    'year': year,
                    'date_pub': year
                })
            
            return articles
    except:
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

def generer_pdf_selectionne(spec, periode, articles):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 20)
    pdf.cell(0, 15, 'VEILLE MEDICALE', 0, 1, 'C')
    pdf.ln(10)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, f'Specialite: {spec}', 0, 1, 'C')
    pdf.cell(0, 8, f'Periode: {periode}', 0, 1, 'C')
    
    for i, article in enumerate(articles, 1):
        pdf.add_page()
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, f'Article {i} - PMID {article["pmid"]}', 0, 1)
        pdf.set_font('Arial', '', 10)
        try:
            title = article['title_fr'].encode('latin-1', 'ignore').decode('latin-1')
        except:
            title = article['title_fr'].encode('ascii', 'ignore').decode('ascii')
        pdf.multi_cell(0, 5, title)
    
    output = io.BytesIO()
    pdf_string = pdf.output(dest='S').encode('latin-1')
    output.write(pdf_string)
    output.seek(0)
    return output.getvalue()

def generer_notebooklm_selectionne(articles):
    contenu = f"""# VEILLE MEDICALE
Date: {datetime.now().strftime("%d/%m/%Y")}

"""
    for i, article in enumerate(articles, 1):
        contenu += f"""
### Article {i}
Titre: {article['title_fr']}
Journal: {article['journal']}
PMID: {article['pmid']}

{article.get('pdf_texte_fr', '')}

---
"""
    return contenu

st.title("🩺 Veille Médicale Professionnelle")

if DEEPL_KEY:
    st.success("✅ DeepL Pro+ activé")
else:
    st.info("ℹ️ Gemini 2.0 Flash")

tab1, tab2, tab3 = st.tabs(["🔍 Recherche", "🔗 Sources", "⚙️ Config"])

with tab1:
    if st.session_state.mode_etape == 1:
        st.header("📋 Étape 1 : Prévisualisation")
        
        with st.sidebar:
            st.header("⚙️ Paramètres")
            
            mode_recherche = st.radio("Mode", ["Par spécialité", "Par mots-clés"])
            
            if mode_recherche == "Par spécialité":
                spec_fr = st.selectbox("🏥 Spécialité", list(TRAD.keys()))
                mots_cles_custom = ""
                
                st.subheader("📰 Journaux")
                choix_journaux = st.radio("Limiter à:", ["Tous PubMed", "Journaux spécialité", "Un journal"])
                
                if choix_journaux == "Un journal":
                    journal_selectionne = st.selectbox("Journal:", JOURNAUX_SPECIALITE.get(spec_fr, []))
                elif choix_journaux == "Journaux spécialité":
                    journal_selectionne = "SPECIALITE"
                else:
                    journal_selectionne = "TOUS"
            else:
                spec_fr = None
                mots_cles_custom = st.text_area("🔎 Mots-clés", height=80)
                journal_selectionne = "TOUS"
            
            st.subheader("📅 Période")
            col1, col2 = st.columns(2)
            with col1:
                date_debut = st.date_input("Début", value=date(2024, 1, 1), format="DD/MM/YYYY")
            with col2:
                date_fin = st.date_input("Fin", value=date.today(), format="DD/MM/YYYY")
            
            st.subheader("🔬 Filtres")
            mode_contenu = st.radio("Type:", ["PDF complets uniquement", "Titre + résumé"])
            type_etude = st.selectbox("Étude", list(TYPES_ETUDE.keys()))
            nb_max = st.slider("Max", 10, 200, 50, 10)
            
            traduire_titres = st.checkbox("🌐 Traduire titres", value=True)
        
        if st.button("🔍 LANCER", type="primary", use_container_width=True):
            if mode_recherche == "Par spécialité":
                term = TRAD[spec_fr]
                display_term = spec_fr
                spec_utilisee = spec_fr
            else:
                if not mots_cles_custom:
                    st.error("⚠️ Entrez mots-clés")
                    st.stop()
                term = traduire_mots_cles(mots_cles_custom)
                display_term = f"Mots-clés: {mots_cles_custom}"
                spec_utilisee = "Personnalisé"
            
            query_parts = [term]
            query_parts.append(f"{date_debut.strftime('%Y/%m/%d')}:{date_fin.strftime('%Y/%m/%d')}[pdat]")
            
            if "PDF complets" in mode_contenu:
                query_parts.append("free full text[sb]")
            
            if journal_selectionne == "SPECIALITE":
                journaux = JOURNAUX_SPECIALITE.get(spec_utilisee, [])
                if journaux:
                    journaux_q = " OR ".join([f'"{j}"[Journal]' for j in journaux])
                    query_parts.append(f"({journaux_q})")
            elif journal_selectionne != "TOUS":
                query_parts.append(f'"{journal_selectionne}"[Journal]')
            
            if TYPES_ETUDE[type_etude]:
                query_parts.append(f"{TYPES_ETUDE[type_etude]}[ptyp]")
            
            query = " AND ".join(query_parts)
            
            base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": nb_max, "sort": "date"}
            
            try:
                with st.spinner("Recherche..."):
                    response = requests.get(base_url, params=params, timeout=15)
                
                if response.status_code != 200:
                    st.error(f"Erreur: {response.status_code}")
                    st.stop()
                
                data = response.json()
                ids = data.get("esearchresult", {}).get("idlist", [])
                count = data.get("esearchresult", {}).get("count", "0")
                
                if not ids:
                    st.warning("Aucun article")
                    st.stop()
                
                st.success(f"✅ {count} articles - {len(ids)} affichés")
                
                with st.spinner("Récupération..."):
                    articles_preview = recuperer_titres_rapides(ids, traduire_titres=traduire_titres)
                
                st.session_state.articles_previsualises = articles_preview
                st.session_state.info_recherche = {
                    'display_term': display_term,
                    'periode': f"du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}",
                    'spec': spec_utilisee,
                    'mode_traduction': 'gemini'
                }
                
                st.session_state.mode_etape = 2
                st.rerun()
            except Exception as e:
                st.error(f"Erreur: {str(e)}")
    
    elif st.session_state.mode_etape == 2:
        st.header("📑 Étape 2 : Sélection")
        
        st.info(f"{st.session_state.info_recherche['display_term']} | {st.session_state.info_recherche['periode']}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Tout"):
                for i in range(len(st.session_state.articles_previsualises)):
                    st.session_state[f"select_{i}"] = True
                st.rerun()
        with col2:
            if st.button("↩️ Nouvelle"):
                st.session_state.mode_etape = 1
                st.session_state.articles_previsualises = []
                st.rerun()
        
        st.divider()
        
        articles_sel = []
        
        for i, article in enumerate(st.session_state.articles_previsualises):
            col_c, col_i = st.columns([0.1, 0.9])
            with col_c:
                selected = st.checkbox("", key=f"select_{i}", label_visibility="collapsed")
            with col_i:
                st.markdown(f"**{i+1}. {article['title_fr']}**")
                st.caption(f"📰 {article['journal']} | {article['year']} | PMID: {article['pmid']}")
            
            if selected:
                articles_sel.append(article['pmid'])
            st.divider()
        
        st.markdown(f"**{len(articles_sel)} sélectionné(s)**")
        
        if 0 < len(articles_sel) <= 20:
            if st.button("🚀 ANALYSER", type="primary", use_container_width=True):
                st.session_state.analyses_individuelles = {}
                
                for idx, pmid in enumerate(articles_sel):
                    st.subheader(f"📄 Article {idx+1}/{len(articles_sel)} - {pmid}")
                    
                    article_info = next((a for a in st.session_state.articles_previsualises if a['pmid'] == pmid), None)
                    if not article_info:
                        continue
                    
                    st.markdown(f"**{article_info['title_fr']}**")
                    
                    status = st.empty()
                    
                    def callback(msg):
                        status.info(msg)
                    
                    pdf_texte, erreur = telecharger_et_extraire_pdf(pmid, progress_callback=callback)
                    status.empty()
                    
                    if pdf_texte:
                        st.success(f"✅ PDF extrait ({len(pdf_texte)} car.)")
                        
                        with st.expander("📄 PDF"):
                            st.text_area("", pdf_texte, height=400, key=f"pdf_{pmid}")
                        
                        with st.spinner("🤖 Analyse..."):
                            try:
                                genai.configure(api_key=G_KEY)
                                model = genai.GenerativeModel('gemini-2.0-flash-exp')
                                
                                prompt = f"""Analyse médicale.

Titre: {article_info['title_fr']}
Journal: {article_info['journal']}

{pdf_texte}

Analyse:
## Objectif
## Méthodologie
## Résultats
## Conclusion"""
                                
                                response = model.generate_content(prompt)
                                analyse = response.text
                                
                                st.markdown("### 🤖 Analyse")
                                st.markdown(analyse)
                                
                                st.session_state.analyses_individuelles[pmid] = {
                                    'pmid': pmid,
                                    'title_fr': article_info['title_fr'],
                                    'journal': article_info['journal'],
                                    'year': article_info['year'],
                                    'pdf_texte_fr': pdf_texte,
                                    'analyse_ia': analyse
                                }
                            except Exception as e:
                                st.error(f"Erreur: {str(e)}")
                    else:
                        st.error(f"❌ {erreur}")
                    
                    st.divider()
                
                if st.session_state.analyses_individuelles:
                    st.session_state.mode_etape = 3
                    st.rerun()
    
    elif st.session_state.mode_etape == 3:
        st.header("📚 Étape 3 : Sélection finale")
        
        articles_finaux_ids = []
        
        for pmid, data in st.session_state.analyses_individuelles.items():
            col_c, col_i = st.columns([0.1, 0.9])
            with col_c:
                include = st.checkbox("", key=f"final_{pmid}", value=True, label_visibility="collapsed")
            with col_i:
                st.markdown(f"**{data['title_fr']}**")
                st.caption(f"{data['journal']} | {data['year']}")
                with st.expander("🤖 Analyse"):
                    st.markdown(data['analyse_ia'])
            
            if include:
                articles_finaux_ids.append(pmid)
            st.divider()
        
        if articles_finaux_ids:
            st.success(f"✅ {len(articles_finaux_ids)} sélectionné(s)")
            
            if st.button("📦 GÉNÉRER", type="primary", use_container_width=True):
                articles_finaux = [st.session_state.analyses_individuelles[pmid] for pmid in articles_finaux_ids]
                
                with st.spinner("Génération..."):
                    pdf_final = generer_pdf_selectionne(
                        st.session_state.info_recherche['spec'],
                        st.session_state.info_recherche['periode'],
                        articles_finaux
                    )
                    notebooklm = generer_notebooklm_selectionne(articles_finaux)
                
                st.session_state.fichiers_finaux = {
                    'pdf': pdf_final,
                    'notebooklm': notebooklm,
                    'articles': articles_finaux
                }
                
                st.session_state.mode_etape = 4
                st.rerun()
    
    elif st.session_state.mode_etape == 4:
        st.header("🎉 Terminé!")
        
        st.success(f"✅ {len(st.session_state.fichiers_finaux['articles'])} article(s)")
        
        st.subheader("📥 Téléchargements")
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "📄 PDF",
                st.session_state.fichiers_finaux['pdf'],
                f"veille_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        with col2:
            st.download_button(
                "🎙️ NotebookLM",
                st.session_state.fichiers_finaux['notebooklm'],
                f"podcast_{datetime.now().strftime('%Y%m%d')}.txt",
                use_container_width=True
            )
        
        st.link_button("🔗 NotebookLM", "https://notebooklm.google.com", use_container_width=True)
        
        if st.button("🔄 Nouvelle", use_container_width=True):
            st.session_state.mode_etape = 1
            st.session_state.articles_previsualises = []
            st.session_state.analyses_individuelles = {}
            st.session_state.fichiers_finaux = {}
            st.rerun()

with tab2:
    st.header("🔗 Sources")
    
    spec_src = st.selectbox("Spécialité:", list(SOURCES_PAR_SPECIALITE.keys()))
    
    for nom, info in SOURCES_PAR_SPECIALITE[spec_src].items():
        with st.expander(f"📚 {nom}"):
            st.markdown(f"**{info['description']}**")
            mots = st.text_input("Rechercher:", key=f"src_{nom}")
            col1, col2 = st.columns(2)
            with col1:
                if mots:
                    st.link_button("🔍", f"{info['recherche']}{mots}")
            with col2:
                st.link_button("🏠", info['url'])

with tab3:
    st.header("⚙️ Config")
    st.info("DeepL Pro+ : 29,99€/mois")

st.caption("💊 Gemini 2.0 Flash")
