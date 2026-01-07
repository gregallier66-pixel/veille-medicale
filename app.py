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
        "CNGOF": {"url": "http://www.cngof.fr", "description": "Collège National Gynécologues Obstétriciens", "recherche": "http://www.cngof.fr/?s="},
        "ACOG": {"url": "https://www.acog.org", "description": "American College Obstetricians Gynecologists", "recherche": "https://www.acog.org/search?q="},
        "RCOG": {"url": "https://www.rcog.org.uk", "description": "Royal College UK", "recherche": "https://www.rcog.org.uk/search?q="},
        "HAS": {"url": "https://www.has-sante.fr", "description": "Haute Autorité Santé", "recherche": "https://www.has-sante.fr/jcms/recherche?text="},
        "SOGC": {"url": "https://www.sogc.org", "description": "Society Obstetricians Canada", "recherche": "https://www.sogc.org/en/content/search.aspx?q="}
    },
    "Obstétrique": {
        "CNGOF": {"url": "http://www.cngof.fr", "description": "CNGOF", "recherche": "http://www.cngof.fr/?s="},
        "ACOG": {"url": "https://www.acog.org", "description": "ACOG", "recherche": "https://www.acog.org/search?q="},
        "WHO": {"url": "https://www.who.int/health-topics/maternal-health", "description": "OMS Santé maternelle", "recherche": "https://www.who.int/search?query="},
        "FIGO": {"url": "https://www.figo.org", "description": "FIGO", "recherche": "https://www.figo.org/?s="}
    },
    "Anesthésie-Réanimation": {
        "SFAR": {"url": "https://sfar.org", "description": "SFAR", "recherche": "https://sfar.org/?s="},
        "ASA": {"url": "https://www.asahq.org", "description": "ASA", "recherche": "https://www.asahq.org/search?q="},
        "ESA": {"url": "https://www.esaic.org", "description": "ESA", "recherche": "https://www.esaic.org/search?q="}
    },
    "Endocrinologie": {
        "SFE": {"url": "https://www.sfendocrino.org", "description": "SFE", "recherche": "https://www.sfendocrino.org/?s="},
        "ADA": {"url": "https://diabetes.org", "description": "ADA", "recherche": "https://diabetes.org/search?q="},
        "EASD": {"url": "https://www.easd.org", "description": "EASD", "recherche": "https://www.easd.org/search?q="}
    },
    "Médecine Générale": {
        "HAS": {"url": "https://www.has-sante.fr", "description": "HAS", "recherche": "https://www.has-sante.fr/jcms/recherche?text="},
        "CNGE": {"url": "https://www.cnge.fr", "description": "CNGE", "recherche": "https://www.cnge.fr/?s="},
        "NICE": {"url": "https://www.nice.org.uk", "description": "NICE", "recherche": "https://www.nice.org.uk/search?q="}
    },
    "Chirurgie Gynécologique": {
        "CNGOF": {"url": "http://www.cngof.fr", "description": "CNGOF", "recherche": "http://www.cngof.fr/?s="},
        "AAGL": {"url": "https://www.aagl.org", "description": "AAGL", "recherche": "https://www.aagl.org/search?q="}
    },
    "Infertilité": {
        "ESHRE": {"url": "https://www.eshre.eu", "description": "ESHRE", "recherche": "https://www.eshre.eu/search?q="},
        "ASRM": {"url": "https://www.asrm.org", "description": "ASRM", "recherche": "https://www.asrm.org/search?q="}
    },
    "Échographie Gynécologique": {
        "ISUOG": {"url": "https://www.isuog.org", "description": "ISUOG", "recherche": "https://www.isuog.org/search.html?q="},
        "CFEF": {"url": "http://www.cfef.org", "description": "CFEF", "recherche": "http://www.cfef.org/?s="}
    },
    "Oncologie": {
        "INCa": {"url": "https://www.e-cancer.fr", "description": "INCa", "recherche": "https://www.e-cancer.fr/Recherche?SearchText="},
        "NCCN": {"url": "https://www.nccn.org", "description": "NCCN", "recherche": "https://www.nccn.org/search?q="},
        "ESMO": {"url": "https://www.esmo.org", "description": "ESMO", "recherche": "https://www.esmo.org/search?q="}
    },
    "Pédiatrie": {
        "SFP": {"url": "https://www.sfpediatrie.com", "description": "SFP", "recherche": "https://www.sfpediatrie.com/?s="},
        "AAP": {"url": "https://www.aap.org", "description": "AAP", "recherche": "https://www.aap.org/search?q="}
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
        
        prompt = f"""Traduis en français professionnel. UNE SEULE traduction.

{texte}"""
        
        response = model.generate_content(prompt)
        traduction = response.text.strip()
        traduction = traduction.replace("**", "").replace("Traduction:", "")
        traduction = re.sub(r'^\d+[\.\)]\s*', '', traduction)
        return nettoyer_titre_complet(traduction)
    except:
        return texte

def obtenir_tous_liens_pdf(pmid):
    """Obtient TOUS les liens PDF possibles incluant DOI et liens externes"""
    try:
        urls = []
        pmc_id = None
        doi = None
        
        # 1. Récupérer les métadonnées complètes
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        fetch_params = {"db": "pubmed", "id": pmid, "retmode": "xml"}
        
        try:
            response = requests.get(fetch_url, params=fetch_params, timeout=10)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                
                # PMC ID
                pmc_elem = root.find('.//ArticleId[@IdType="pmc"]')
                if pmc_elem is not None:
                    pmc_id = pmc_elem.text.replace("PMC", "")
                
                # DOI
                doi_elem = root.find('.//ArticleId[@IdType="doi"]')
                if doi_elem is not None:
                    doi = doi_elem.text
        except:
            pass
        
        # 2. Si PMC ID trouvé, ajouter URLs PMC
        if pmc_id:
            urls.extend([
                f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/",
                f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/main.pdf",
                f"https://europepmc.org/articles/PMC{pmc_id}?pdf=render",
                f"https://europepmc.org/backend/ptpmcrender.fcgi?accid=PMC{pmc_id}&blobtype=pdf"
            ])
        
        # 3. Si DOI trouvé, ajouter liens éditeurs
        if doi:
            # DOI direct
            urls.append(f"https://doi.org/{doi}")
            
            # Unpaywall (accès ouvert)
            urls.append(f"https://api.unpaywall.org/v2/{doi}?email=research@example.com")
        
        # 4. eLink vers PMC (backup)
        try:
            elink_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
            elink_params = {"dbfrom": "pubmed", "db": "pmc", "id": pmid, "retmode": "xml"}
            elink_response = requests.get(elink_url, params=elink_params, timeout=10)
            
            if elink_response.status_code == 200:
                elink_root = ET.fromstring(elink_response.content)
                elink_pmc = elink_root.find('.//Link/Id')
                if elink_pmc is not None and not pmc_id:
                    pmc_id = elink_pmc.text
                    urls.extend([
                        f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/",
                        f"https://europepmc.org/articles/PMC{pmc_id}?pdf=render"
                    ])
        except:
            pass
        
        return urls, pmc_id, doi
        
    except Exception as e:
        return [], None, None

def telecharger_et_extraire_pdf(pmid, mode_traduction="gemini", progress_callback=None):
    """Version ULTRA optimisée avec unpaywall et multiples sources"""
    try:
        urls_possibles, pmc_id, doi = obtenir_tous_liens_pdf(pmid)
        
        if not urls_possibles:
            return None, "PDF non disponible en libre accès"
        
        if progress_callback:
            progress_callback(f"📥 Recherche PDF PMID {pmid}...")
        
        pdf_content = None
        url_reussie = None
        
        # User-Agents variés
        headers_list = [
            {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            },
            {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'application/pdf'
            },
            {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
                'Accept': 'application/pdf,text/html'
            }
        ]
        
        # Essayer CHAQUE URL avec CHAQUE header
        for url in urls_possibles:
            if pdf_content:
                break
            
            # Cas spécial : Unpaywall API
            if 'unpaywall.org' in url:
                try:
                    resp = requests.get(url, timeout=15)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get('is_oa') and data.get('best_oa_location'):
                            pdf_url = data['best_oa_location'].get('url_for_pdf')
                            if pdf_url:
                                urls_possibles.insert(0, pdf_url)
                except:
                    pass
                continue
            
            for headers in headers_list:
                try:
                    response = requests.get(
                        url,
                        timeout=30,
                        allow_redirects=True,
                        headers=headers,
                        stream=True
                    )
                    
                    if response.status_code == 200:
                        content_type = response.headers.get('Content-Type', '').lower()
                        
                        # Lire le début du contenu
                        content_preview = response.content[:20]
                        
                        # Vérifier si c'est un PDF
                        is_pdf = (
                            b'%PDF' in content_preview or
                            'application/pdf' in content_type or
                            'pdf' in content_type
                        )
                        
                        if is_pdf:
                            pdf_content = response.content
                            url_reussie = url
                            if progress_callback:
                                progress_callback(f"✅ PDF trouvé ({len(pdf_content)} bytes)")
                            break
                
                except Exception as e:
                    continue
                
                time.sleep(0.2)
        
        if not pdf_content:
            msg_erreur = "PDF non accessible"
            if pmc_id:
                msg_erreur += f" (PMC{pmc_id})"
            if doi:
                msg_erreur += f" - DOI: {doi}"
            msg_erreur += ". Abonnement institutionnel peut être nécessaire."
            return None, msg_erreur
        
        if progress_callback:
            progress_callback(f"📄 Extraction texte...")
        
        try:
            pdf_file = BytesIO(pdf_content)
            pdf_reader = pypdf.PdfReader(pdf_file)
            
            texte_complet = ""
            nb_pages = len(pdf_reader.pages)
            max_pages = min(nb_pages, 15)
            
            for i in range(max_pages):
                try:
                    texte_page = pdf_reader.pages[i].extract_text()
                    if texte_page:
                        texte_complet += texte_page + "\n\n"
                except:
                    continue
            
            if len(texte_complet) < 100:
                return None, "Contenu PDF insuffisant"
            
            if len(texte_complet) > 12000:
                texte_complet = texte_complet[:12000] + "\n\n[Tronqué]"
            
            if progress_callback:
                progress_callback(f"🌐 Traduction...")
            
            # Traduction
            chunk_size = 4000
            texte_traduit = ""
            
            for i in range(0, len(texte_complet), chunk_size):
                chunk = texte_complet[i:i+chunk_size]
                trad = traduire_texte(chunk, mode=mode_traduction)
                texte_traduit += trad + "\n\n"
                
                if progress_callback and i > 0:
                    pct = min(100, int((i/len(texte_complet))*100))
                    progress_callback(f"🌐 Traduction {pct}%...")
            
            return texte_traduit, None
            
        except Exception as e:
            return None, f"Erreur extraction: {str(e)}"
            
    except Exception as e:
        return None, f"Erreur: {str(e)}"

def traduire_mots_cles(mots):
    """Traduit les mots-clés français en termes médicaux anglais"""
    try:
        genai.configure(api_key=G_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        prompt = f"""Traduis ces termes médicaux français en anglais médical standard pour PubMed.

RÈGLES:
- Utilise la terminologie MeSH (Medical Subject Headings)
- Donne UNIQUEMENT les termes anglais, sans explication
- Pas de guillemets, pas de ponctuation superflue
- Variantes orthographiques acceptées

Exemples:
dysménorrhée → dysmenorrhea
hypertension gravidique → gestational hypertension
pré-éclampsie → preeclampsia

Termes à traduire: {mots}

Traduction:"""
        
        response = model.generate_content(prompt)
        traduction = response.text.strip()
        
        # Nettoyer
        traduction = traduction.replace('"', '').replace("'", "")
        traduction = traduction.replace("→", "").replace(":", "")
        traduction = traduction.strip()
        
        return traduction
    except Exception as e:
        # Fallback : retourner tel quel
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
                
                month = article.find('.//PubDate/Month')
                month = month.text if month is not None else ""
                
                day = article.find('.//PubDate/Day')
                day = day.text if day is not None else ""
                
                if month and day:
                    date_pub = f"{day}/{month}/{year}"
                elif month:
                    date_pub = f"{month} {year}"
                else:
                    date_pub = year
                
                articles.append({
                    'pmid': pmid,
                    'title': title,
                    'title_fr': title_fr,
                    'journal': journal,
                    'year': year,
                    'date_pub': date_pub
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
        pdf.ln(2)
        pdf.cell(0, 5, f"{article['journal']} - {article['year']}", 0, 1)
    
    output = io.BytesIO()
    pdf_string = pdf.output(dest='S').encode('latin-1')
    output.write(pdf_string)
    output.seek(0)
    return output.getvalue()

def generer_notebooklm_selectionne(articles):
    contenu = f"""# VEILLE MEDICALE - PODCAST
Date: {datetime.now().strftime("%d/%m/%Y")}

"""
    for i, article in enumerate(articles, 1):
        contenu += f"""
### Article {i}
Titre: {article['title_fr']}
Journal: {article['journal']} ({article['year']})
PMID: {article['pmid']}

Contenu:
{article.get('pdf_texte_fr', 'Non disponible')}

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
            
            mode_recherche = st.radio("Mode de recherche", ["Par spécialité", "Par mots-clés"])
            
            # CORRECTION : Options complètes pour les DEUX modes
            if mode_recherche == "Par spécialité":
                spec_fr = st.selectbox("🏥 Spécialité", list(TRAD.keys()))
                mots_cles_custom = ""
                spec_combo = None
                
                st.subheader("📰 Journaux")
                choix_journaux = st.radio(
                    "Limiter la recherche à:",
                    ["Tous les journaux PubMed", "Journaux de la spécialité uniquement", "Un journal spécifique"]
                )
                
                if choix_journaux == "Un journal spécifique":
                    journaux_dispo = JOURNAUX_SPECIALITE.get(spec_fr, [])
                    journal_selectionne = st.selectbox("Choisir le journal:", journaux_dispo)
                elif choix_journaux == "Journaux de la spécialité uniquement":
                    journal_selectionne = "SPECIALITE"
                else:
                    journal_selectionne = "TOUS"
                    
            else:  # Par mots-clés
                spec_fr = None
                mots_cles_custom = st.text_area("🔎 Mots-clés", placeholder="Ex: hypertension gravidique", height=80)
                
                # AJOUT : Choix spécialité optionnel pour mots-clés
                inclure_specialite = st.checkbox("🔬 Cibler une spécialité", value=False)
                
                if inclure_specialite:
                    spec_combo = st.selectbox("Spécialité:", list(TRAD.keys()))
                    
                    st.subheader("📰 Journaux")
                    choix_journaux = st.radio(
                        "Limiter la recherche à:",
                        ["Tous les journaux PubMed",
                         "Journaux de la spécialité uniquement",
                         "Un journal spécifique"]
                    )
                    
                    if choix_journaux == "Un journal spécifique":
                        journaux_dispo = JOURNAUX_SPECIALITE.get(spec_combo, [])
                        journal_selectionne = st.selectbox("Choisir le journal:", journaux_dispo)
                    elif choix_journaux == "Journaux de la spécialité uniquement":
                        journal_selectionne = "SPECIALITE"
                    else:
                        journal_selectionne = "TOUS"
                else:
                    spec_combo = None
                    journal_selectionne = "TOUS"
                    st.info("🌐 Recherche dans TOUS les journaux PubMed (30 000+ revues)")
            
            st.subheader("📅 Période")
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Début**")
                date_debut = st.date_input("Début", value=date(2024, 1, 1), format="DD/MM/YYYY", label_visibility="collapsed")
            with col2:
                st.write("**Fin**")
                date_fin = st.date_input("Fin", value=date.today(), format="DD/MM/YYYY", label_visibility="collapsed")
            
            st.subheader("🔬 Filtres")
            mode_contenu = st.radio("Type de contenu:", ["PDF complets uniquement", "Titre + résumé"])
            type_etude = st.selectbox("Type d'étude", list(TYPES_ETUDE.keys()))
            nb_max = st.slider("Nombre max de résultats", 10, 200, 50, 10)
            
            traduire_titres = st.checkbox("🌐 Traduire les titres en français", value=True)
        
        if st.button("🔍 LANCER LA RECHERCHE", type="primary", use_container_width=True):
            
            # Construction requête
            if mode_recherche == "Par spécialité":
                term = TRAD[spec_fr]
                display_term = spec_fr
                spec_utilisee = spec_fr
            else:
                if not mots_cles_custom:
                    st.error("⚠️ Veuillez entrer des mots-clés")
                    st.stop()
                
                with st.spinner("🌐 Traduction des mots-clés..."):
                    term = traduire_mots_cles(mots_cles_custom)
                
                # AFFICHER la traduction
                with st.expander("🔍 Aperçu traduction"):
                    st.markdown(f"**Français:** {mots_cles_custom}")
                    st.markdown(f"**Anglais (PubMed):** `{term}`")
                
                display_term = f"Mots-clés: {mots_cles_custom}"
                
                if inclure_specialite and spec_combo:
                    term = f"{term} AND {TRAD[spec_combo]}"
                    spec_utilisee = spec_combo
                else:
                    spec_utilisee = "Personnalisé"
            
            query_parts = [term]
            query_parts.append(f"{date_debut.strftime('%Y/%m/%d')}:{date_fin.strftime('%Y/%m/%d')}[pdat]")
            
            if "PDF complets" in mode_contenu:
                query_parts.append("free full text[sb]")
            
            # Gestion journaux
            if journal_selectionne == "SPECIALITE":
                journaux = JOURNAUX_SPECIALITE.get(spec_utilisee if mode_recherche == "Par spécialité" else spec_combo, [])
                if journaux:
                    journaux_q = " OR ".join([f'"{j}"[Journal]' for j in journaux])
                    query_parts.append(f"({journaux_q})")
            elif journal_selectionne != "TOUS":
                query_parts.append(f'"{journal_selectionne}"[Journal]')
            
            if TYPES_ETUDE[type_etude]:
                query_parts.append(f"{TYPES_ETUDE[type_etude]}[ptyp]")
            
            query = " AND ".join(query_parts)
            
            # AFFICHER la requête complète
            with st.expander("🔍 Requête PubMed complète"):
                st.code(query, language="text")
                st.caption("Cette requête est envoyée à PubMed pour rechercher les articles")
            
            base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": nb_max, "sort": "date"}
            
            try:
                with st.spinner("🔎 Recherche en cours sur PubMed..."):
                    response = requests.get(base_url, params=params, timeout=15)
                
                if response.status_code != 200:
                    st.error(f"Erreur: {response.status_code}")
                    st.stop()
                
                data = response.json()
                ids = data.get("esearchresult", {}).get("idlist", [])
                count = data.get("esearchresult", {}).get("count", "0")
                
                if not ids:
                    st.warning(f"⚠️ Aucun article trouvé")
                    
                    st.info("""
**Suggestions pour améliorer les résultats:**

1. **Élargir la période** (ex: 2020-2025)
2. **Retirer les filtres restrictifs:**
   - Désactiver "PDF complets uniquement"
   - Mettre "Tous les journaux"
   - Retirer le filtre type d'étude
3. **Modifier les mots-clés:**
   - Essayer des synonymes
   - Utiliser des termes plus généraux
   - Retirer les accents

**Exemple:** Au lieu de "dysménorrhée", essayez "douleur menstruelle"
                    """)
                    
                    with st.expander("🔍 Vérifier la traduction"):
                        st.markdown(f"**Votre recherche:** {mots_cles_custom if mode_recherche == 'Par mots-clés' else spec_fr}")
                        st.markdown(f"**Terme utilisé sur PubMed:** `{term}`")
                        st.markdown(f"**Requête complète:** `{query}`")
                        st.markdown("""
**Conseil:** Vérifiez que le terme anglais est correct. 
Par exemple, "dysmenorrhea" devrait donner des résultats.
                        """)
                    
                    st.stop()
                
                st.success(f"✅ {count} articles trouvés - Affichage de {len(ids)}")
                
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
            if st.button("✅ Tout sélectionner"):
                for i in range(len(st.session_state.articles_previsualises)):
                    st.session_state[f"select_{i}"] = True
                st.rerun()
        with col2:
            if st.button("↩️ Nouvelle recherche"):
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
                st.markdown(f"📰 {article['journal']} | 📅 {article['date_pub']} | [PMID {article['pmid']}](https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/)")
            
            if selected:
                articles_sel.append(article['pmid'])
            st.divider()
        
        st.markdown(f"**{len(articles_sel)} sélectionné(s)**")
        
        if 0 < len(articles_sel) <= 20:
            if st.button("🚀 ANALYSER", type="primary", use_container_width=True):
                st.session_state.analyses_individuelles = {}
                
                for idx, pmid in enumerate(articles_sel):
                    st.subheader(f"📄 Article {idx+1}/{len(articles_sel)}")
                    
                    article_info = next((a for a in st.session_state.articles_previsualises if a['pmid'] == pmid), None)
                    if not article_info:
                        continue
                    
                    st.markdown(f"**{article_info['title_fr']}**")
                    st.markdown(f"[🔗 Voir sur PubMed](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)")
                    
                    status = st.empty()
                    
                    def callback(msg):
                        status.info(msg)
                    
                    pdf_texte, erreur = telecharger_et_extraire_pdf(pmid, progress_callback=callback)
                    status.empty()
                    
                    if pdf_texte:
                        st.success(f"✅ PDF extrait et traduit ({len(pdf_texte)} car.)")
                        
                        with st.expander("📄 Lire le PDF traduit"):
                            st.text_area("", pdf_texte, height=400, key=f"pdf_{pmid}")
                        
                        with st.spinner("🤖 Analyse IA..."):
                            try:
                                genai.configure(api_key=G_KEY)
                                model = genai.GenerativeModel('gemini-2.0-flash-exp')
                                
                                prompt = f"""Analyse médicale approfondie.

Titre: {article_info['title_fr']}

{pdf_texte}

Analyse structurée:
## Objectif
## Méthodologie
## Résultats principaux
## Implications cliniques
## Limites
## Conclusion"""
                                
                                response = model.generate_content(prompt)
                                analyse = response.text
                                
                                st.markdown("### 🤖 Analyse IA")
                                st.markdown(analyse)
                                
                                st.session_state.analyses_individuelles[pmid] = {
                                    'pmid': pmid,
                                    'title_fr': article_info['title_fr'],
                                    'journal': article_info['journal'],
                                    'year': article_info['year'],
                                    'date_pub': article_info['date_pub'],
                                    'pdf_texte_fr': pdf_texte,
                                    'analyse_ia': analyse
                                }
                            except Exception as e:
                                st.error(f"Erreur analyse: {str(e)}")
                    else:
                        st.error(f"❌ {erreur}")
                        st.info(f"💡 L'article est peut-être accessible via votre institution : [Voir sur PubMed](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)")
                    
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
                st.caption(f"{data['journal']} | {data['date_pub']}")
                with st.expander("🤖 Voir l'analyse"):
                    st.markdown(data['analyse_ia'])
            
            if include:
                articles_finaux_ids.append(pmid)
            st.divider()
        
        if articles_finaux_ids:
            st.success(f"✅ {len(articles_finaux_ids)} sélectionné(s)")
            
            if st.button("📦 GÉNÉRER LES FICHIERS", type="primary", use_container_width=True):
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
        st.header("🎉 Veille terminée!")
        
        st.success(f"✅ {len(st.session_state.fichiers_finaux['articles'])} article(s) analysé(s)")
        
        st.subheader("📋 Récapitulatif")
        for i, article in enumerate(st.session_state.fichiers_finaux['articles'], 1):
            with st.expander(f"📄 Article {i} - {article['title_fr'][:60]}..."):
                st.markdown(f"**Journal:** {article['journal']} ({article['year']})")
                st.markdown(f"**PMID:** [{article['pmid']}](https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/)")
                st.markdown("### 🤖 Analyse")
                st.markdown(article['analyse_ia'])
        
        st.divider()
        st.subheader("📥 Téléchargements")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.download_button(
                "📄 Télécharger PDF",
                st.session_state.fichiers_finaux['pdf'],
                f"veille_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        
        with col2:
            with st.expander("📋 Voir le texte NotebookLM"):
                st.text_area(
                    "Copier/coller dans NotebookLM:",
                    st.session_state.fichiers_finaux['notebooklm'],
                    height=400
                )
            
            st.download_button(
                "💾 Télécharger NotebookLM",
                st.session_state.fichiers_finaux['notebooklm'],
                f"podcast_{datetime.now().strftime('%Y%m%d')}.txt",
                use_container_width=True
            )
        
        st.info("💡 **Mobile** : Utilisez l'expander ci-dessus pour copier/coller le texte")
        st.link_button("🔗 Ouvrir NotebookLM", "https://notebooklm.google.com", use_container_width=True)
        
        if st.button("🔄 Nouvelle recherche", use_container_width=True):
            st.session_state.mode_etape = 1
            st.session_state.articles_previsualises = []
            st.session_state.analyses_individuelles = {}
            st.session_state.fichiers_finaux = {}
            st.rerun()

with tab2:
    st.header("🔗 Sources complémentaires")
    
    spec_src = st.selectbox("Choisir une spécialité:", list(SOURCES_PAR_SPECIALITE.keys()))
    
    st.markdown(f"### {len(SOURCES_PAR_SPECIALITE[spec_src])} sources pour {spec_src}")
    
    for nom, info in SOURCES_PAR_SPECIALITE[spec_src].items():
        with st.expander(f"📚 {nom}"):
            st.markdown(f"**{info['description']}**")
            st.link_button("🏠 Site officiel", info['url'])
            
            mots = st.text_input("Rechercher dans cette source:", key=f"src_{nom}")
            if mots:
                st.link_button("🔍 Lancer la recherche", f"{info['recherche']}{mots}")

with tab3:
    st.header("⚙️ Configuration")
    
    st.markdown("""
## 🌐 DeepL Pro+

**Tarif:** 29,99€/mois  
**Volume:** 1 million caractères/mois

### Installation
1. S'inscrire sur https://www.deepl.com/pro#developer
2. Choisir "API Pro+"
3. Copier la clé API
4. Ajouter dans Settings → Secrets:
```toml
DEEPL_KEY = "votre-clé-ici"
```

### Résiliation
Simple et rapide : Account → Subscription → Cancel  
✅ Sans engagement
    """)
    
    if DEEPL_KEY:
        st.success("✅ DeepL Pro+ configuré")
    else:
        st.info("ℹ️ Traduction : Gemini 2.0 Flash (gratuit)")

st.caption("💊 Veille médicale professionnelle | Gemini 2.0 Flash")
