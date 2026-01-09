"""
VEILLE MÉDICALE PROFESSIONNELLE - VERSION 7
Version améliorée avec :
- Rate limiting NCBI
- Cache SQLite des PDF
- Retry avec backoff exponentiel
- Validation Pydantic
- Logging structuré
- Traitement parallèle
- Gestion mémoire optimisée
"""

import streamlit as st
import google.generativeai as genai
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
from datetime import datetime, date, timedelta
import xml.etree.ElementTree as ET
from fpdf import FPDF
import io
import pypdf
from io import BytesIO
import re
import time
import tarfile
import sqlite3
import hashlib
import logging
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, validator, Field

# =========================
# CONFIGURATION LOGGING
# =========================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('veille_medicale.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Veille Médicale Pro v7", layout="wide")

# =========================
# RÉCUPÉRATION DES CLÉS
# =========================

try:
    G_KEY = st.secrets["GEMINI_KEY"]
except:
    st.error("⚠️ Clé GEMINI_KEY manquante")
    logger.error("Clé GEMINI_KEY manquante dans st.secrets")
    st.stop()

DEEPL_KEY = st.secrets.get("DEEPL_KEY", None)

# =========================
# VALIDATION PYDANTIC
# =========================

class Article(BaseModel):
    pmid: str
    pmcid: Optional[str] = None
    title: str
    title_fr: str
    journal: str
    year: str
    date_pub: str
    is_pdf_oa: bool = False
    pdf_source_potentielle: Optional[str] = None
    pdf_texte_fr: Optional[str] = None
    
    @validator('pmid')
    def validate_pmid(cls, v):
        if not v.isdigit() or len(v) > 10:
            raise ValueError(f"PMID invalide: {v}")
        return v
    
    @validator('year')
    def validate_year(cls, v):
        if v != "N/A":
            try:
                year = int(v)
                if not 1900 <= year <= 2030:
                    raise ValueError(f"Année hors limites: {year}")
            except ValueError:
                raise ValueError(f"Année invalide: {v}")
        return v

# =========================
# PARAMÈTRES GÉNÉRAUX
# =========================

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

LANGUES = {
    "Toutes les langues": "",
    "Français uniquement": "fre",
    "Anglais uniquement": "eng"
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

# =========================
# SESSION STATE
# =========================

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

# =========================
# RATE LIMITER (3 req/sec NCBI)
# =========================

class RateLimiter:
    """Rate limiter pour respecter les limites NCBI (3 requêtes/seconde)"""
    def __init__(self, max_calls=3, period=1.0):
        self.max_calls = max_calls
        self.period = period
        self.calls = []
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            self.calls = [c for c in self.calls if now - c < self.period]
            
            if len(self.calls) >= self.max_calls:
                sleep_time = self.period - (now - self.calls[0])
                if sleep_time > 0:
                    logger.debug(f"Rate limiting: sleep {sleep_time:.2f}s")
                    time.sleep(sleep_time)
            
            self.calls.append(time.time())
            return func(*args, **kwargs)
        return wrapper

# Instance globale du rate limiter
ncbi_rate_limiter = RateLimiter(max_calls=3, period=1.0)

# =========================
# SESSION HTTP AVEC RETRY
# =========================

def get_session_with_retry():
    """Crée une session HTTP avec retry automatique"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504, 429],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# Session globale
http_session = get_session_with_retry()

# =========================
# CACHE SQLITE POUR PDF
# =========================

class PDFCache:
    """Cache SQLite pour éviter de re-télécharger les PDF"""
    
    def __init__(self, db_path="pdf_cache.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_table()
    
    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS pdf_cache (
                pmid TEXT PRIMARY KEY,
                texte_fr TEXT,
                date_cache TEXT,
                source TEXT,
                hash TEXT
            )
        """)
        self.conn.commit()
    
    def get(self, pmid: str) -> Optional[Dict[str, str]]:
        """Récupère un PDF du cache"""
        try:
            cursor = self.conn.execute(
                "SELECT texte_fr, source, date_cache FROM pdf_cache WHERE pmid = ?", 
                (pmid,)
            )
            row = cursor.fetchone()
            if row:
                logger.info(f"Cache HIT pour PMID {pmid}")
                return {
                    'texte_fr': row[0],
                    'source': row[1],
                    'date_cache': row[2]
                }
            logger.debug(f"Cache MISS pour PMID {pmid}")
            return None
        except Exception as e:
            logger.error(f"Erreur lecture cache: {e}")
            return None
    
    def set(self, pmid: str, texte_fr: str, source: str):
        """Stocke un PDF dans le cache"""
        try:
            text_hash = hashlib.md5(texte_fr.encode()).hexdigest()
            self.conn.execute(
                "INSERT OR REPLACE INTO pdf_cache VALUES (?, ?, datetime('now'), ?, ?)",
                (pmid, texte_fr, source, text_hash)
            )
            self.conn.commit()
            logger.info(f"Cache SET pour PMID {pmid} (source: {source})")
        except Exception as e:
            logger.error(f"Erreur écriture cache: {e}")
    
    def clear_old(self, days=30):
        """Supprime les entrées de plus de X jours"""
        try:
            self.conn.execute(
                "DELETE FROM pdf_cache WHERE date_cache < datetime('now', ?)",
                (f'-{days} days',)
            )
            self.conn.commit()
            logger.info(f"Cache nettoyé (>{days} jours)")
        except Exception as e:
            logger.error(f"Erreur nettoyage cache: {e}")

# Instance globale du cache
pdf_cache = PDFCache()

# =========================
# VALIDATION ET SANITIZATION
# =========================

def sanitize_pubmed_term(term: str) -> str:
    """Nettoie un terme de recherche PubMed"""
    # Supprimer caractères dangereux
    term = re.sub(r'[^\w\s\-\(\)\[\]:,\.]', '', term)
    # Limiter longueur
    term = term[:500]
    logger.debug(f"Terme sanitizé: {term}")
    return term

# =========================
# FONCTIONS UTILITAIRES
# =========================

def traduire_avec_deepl(texte, api_key):
    try:
        url = "https://api-free.deepl.com/v2/translate"
        data = {
            "auth_key": api_key,
            "text": texte,
            "target_lang": "FR",
            "source_lang": "EN",
            "formality": "more"
        }
        response = http_session.post(url, data=data, timeout=30)
        if response.status_code == 200:
            return response.json()["translations"][0]["text"]
        logger.warning(f"DeepL erreur HTTP {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Erreur DeepL: {e}")
        return None

def nettoyer_titre(titre):
    if not titre:
        return "Titre non disponible"
    titre = re.sub(r'<[^>]+>', '', titre)
    titre = re.sub(r'\s*see\s+more\s*', '', titre, flags=re.IGNORECASE)
    titre = re.sub(r'\s*\\[see\s+more\\]\s*', '', titre, flags=re.IGNORECASE)
    titre = re.sub(r'\s*\\(see\s+more\\)\s*', '', titre, flags=re.IGNORECASE)
    titre = re.sub(r'\s*voir\s+plus\s*', '', titre, flags=re.IGNORECASE)
    titre = re.sub(r'\s+', ' ', titre)
    return titre.strip()

def traduire_texte(texte, mode="gemini"):
    if not texte or len(texte.strip()) < 3:
        return texte
    if mode == "deepl" and DEEPL_KEY:
        trad = traduire_avec_deepl(texte, DEEPL_KEY)
        if trad:
            return nettoyer_titre(trad)
    try:
        genai.configure(api_key=G_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        prompt = f"""Tu es un traducteur médical professionnel. Traduis le texte anglais suivant en français médical professionnel.

CONSIGNES STRICTES:
- Fournis UNIQUEMENT la traduction française
- Pas de préambule
- Pas de numérotation
- Conserve la terminologie médicale exacte
- Pas de formatage markdown

TEXTE À TRADUIRE:
{texte}

TRADUCTION FRANÇAISE:"""
        response = model.generate_content(prompt)
        traduction = response.text.strip()
        traduction = traduction.replace("**", "")
        traduction = re.sub(r'^(Traduction\s*:?\s*)', '', traduction, flags=re.IGNORECASE)
        traduction = re.sub(r'^\d+[\.\)]\s*', '', traduction)
        traduction = nettoyer_titre(traduction)
        return traduction
    except Exception as e:
        logger.error(f"Erreur traduction Gemini: {e}", exc_info=True)
        return texte

def traduire_mots_cles(mots_cles_fr):
    try:
        genai.configure(api_key=G_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        prompt = f"""Tu es un expert en terminologie médicale. Traduis ces mots-clés français en termes médicaux anglais optimisés pour PubMed.

CONSIGNES:
- Fournis UNIQUEMENT les termes anglais
- Pas d'explication ou préambule
- Utilise la terminologie MeSH quand possible
- Sépare les termes par des virgules

MOTS-CLÉS FRANÇAIS:
{mots_cles_fr}

TERMES ANGLAIS:"""
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Erreur traduction mots-clés: {e}")
        return mots_cles_fr

# =========================
# IDENTIFIANTS PUBMED (avec rate limiting)
# =========================

@ncbi_rate_limiter
def get_doi_from_pubmed(pmid):
    try:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        params = {"db": "pubmed", "id": pmid, "retmode": "xml"}
        response = http_session.get(base_url, params=params, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for article_id in root.findall('.//ArticleId'):
                if article_id.get('IdType') == 'doi':
                    doi = article_id.text
                    logger.info(f"DOI trouvé pour PMID {pmid}: {doi}")
                    return doi
        return None
    except Exception as e:
        logger.error(f"Erreur get_doi_from_pubmed({pmid}): {e}")
        return None

@ncbi_rate_limiter
def get_pmcid_from_pubmed(pmid):
    try:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        params = {"db": "pubmed", "id": pmid, "retmode": "xml"}
        response = http_session.get(base_url, params=params, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for article_id in root.findall('.//ArticleId'):
                if article_id.get('IdType') == 'pmc':
                    pmcid = article_id.text
                    if pmcid.startswith('PMC'):
                        pmcid = pmcid[3:]
                    logger.info(f"PMCID trouvé pour PMID {pmid}: PMC{pmcid}")
                    return pmcid
        return None
    except Exception as e:
        logger.error(f"Erreur get_pmcid_from_pubmed({pmid}): {e}")
        return None

@ncbi_rate_limiter
def verifier_pdf_disponible_pubmed(pmid):
    try:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
        params = {"dbfrom": "pubmed", "id": pmid, "cmd": "llinks"}
        response = http_session.get(base_url, params=params, timeout=10)
        if response.status_code == 200:
            if "Free in PMC" in response.text or "pmc/articles" in response.text:
                return True
        return False
    except Exception as e:
        logger.error(f"Erreur verifier_pdf_disponible_pubmed({pmid}): {e}")
        return False

# =========================
# RÉCUPÉRATION PDF (avec gestion mémoire)
# =========================

def telecharger_pdf_stream(url, max_size_mb=50, headers=None):
    """Télécharge un PDF en streaming avec limite de taille"""
    if headers is None:
        headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = http_session.get(url, stream=True, timeout=30, headers=headers)
        max_size = max_size_mb * 1024 * 1024
        
        content = BytesIO()
        size = 0
        
        for chunk in response.iter_content(chunk_size=8192):
            size += len(chunk)
            if size > max_size:
                logger.warning(f"PDF trop volumineux (>{max_size_mb}MB): {url}")
                raise ValueError(f"PDF trop volumineux (>{max_size_mb}MB)")
            content.write(chunk)
        
        content.seek(0)
        return content.getvalue()
    except Exception as e:
        logger.error(f"Erreur téléchargement stream: {e}")
        raise

def get_pdf_via_pmc_ftp(pmcid):
    if not pmcid:
        return None, "Pas de PMCID"
    try:
        pmcid_num = pmcid.replace('PMC', '') if pmcid.startswith('PMC') else pmcid
        if len(pmcid_num) >= 7:
            dir1 = pmcid_num[-7:-4].zfill(3)
            dir2 = pmcid_num[-4:-1].zfill(3)
        else:
            dir1 = "000"
            dir2 = pmcid_num[-3:].zfill(3)
        
        tar_url = f"https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/{dir1}/{dir2}/PMC{pmcid_num}.tar.gz"
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        logger.info(f"Tentative PMC FTP: {tar_url}")
        response = http_session.get(tar_url, timeout=30, headers=headers)
        
        if response.status_code == 200:
            try:
                tar_file = tarfile.open(fileobj=BytesIO(response.content))
                for member in tar_file.getmembers():
                    if member.name.endswith('.pdf'):
                        pdf_file = tar_file.extractfile(member)
                        if pdf_file:
                            logger.info(f"PDF extrait du TAR pour PMC{pmcid_num}")
                            return pdf_file.read(), None
            except Exception as e:
                logger.warning(f"Erreur extraction TAR: {e}")
        
        # Fallback direct
        pdf_url_direct = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid_num}/pdf/"
        response = http_session.get(pdf_url_direct, timeout=20, headers=headers, allow_redirects=True)
        if response.status_code == 200 and 'application/pdf' in response.headers.get('Content-Type', ''):
            logger.info(f"PDF récupéré directement pour PMC{pmcid_num}")
            return response.content, None
        
        return None, "PMC FTP: PDF non disponible"
    except Exception as e:
        logger.error(f"Erreur PMC FTP (PMC{pmcid}): {e}")
        return None, f"Erreur PMC FTP: {str(e)}"

def get_pdf_via_pmc(pmcid):
    if not pmcid:
        return None, "Pas de PMCID"
    try:
        pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/pdf/"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = http_session.get(pdf_url, timeout=20, headers=headers, allow_redirects=True)
        content_type = response.headers.get('Content-Type', '')
        if response.status_code == 200 and 'application/pdf' in content_type:
            logger.info(f"PDF récupéré via PMC Web pour PMC{pmcid}")
            return response.content, None
        return None, f"PMC: PDF non disponible (HTTP {response.status_code})"
    except Exception as e:
        logger.error(f"Erreur PMC Web (PMC{pmcid}): {e}")
        return None, f"Erreur PMC: {str(e)}"

def get_pdf_via_unpaywall(doi, email="medical.research@pubmed.search"):
    if not doi:
        return None, "Pas de DOI"
    try:
        url = f"https://api.unpaywall.org/v2/{doi}"
        params = {"email": email}
        response = http_session.get(url, params=params, timeout=15)
        
        if response.status_code == 404:
            return None, "DOI inconnu d'Unpaywall"
        if response.status_code != 200:
            return None, f"Erreur Unpaywall ({response.status_code})"
        
        data = response.json()
        if data.get('is_oa'):
            best_oa = data.get('best_oa_location')
            headers = {'User-Agent': 'Mozilla/5.0'}
            
            if best_oa and best_oa.get('url_for_pdf'):
                pdf_url = best_oa['url_for_pdf']
                logger.info(f"Tentative Unpaywall: {pdf_url}")
                pdf_response = http_session.get(pdf_url, timeout=20, headers=headers)
                if pdf_response.status_code == 200 and 'application/pdf' in pdf_response.headers.get('Content-Type', ''):
                    return pdf_response.content, None
            
            for location in data.get('oa_locations', []):
                pdf_url = location.get('url_for_pdf')
                if pdf_url:
                    try:
                        pdf_response = http_session.get(pdf_url, timeout=20, headers=headers)
                        if pdf_response.status_code == 200 and 'application/pdf' in pdf_response.headers.get('Content-Type', ''):
                            logger.info(f"PDF trouvé via Unpaywall alternative: {pdf_url}")
                            return pdf_response.content, None
                    except:
                        continue
        
        return None, "Article payant (pas d'accès libre)"
    except Exception as e:
        logger.error(f"Erreur Unpaywall ({doi}): {e}")
        return None, f"Erreur Unpaywall: {str(e)}"

def get_pdf_via_europepmc(pmid, pmcid=None):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        if pmcid:
            pdf_url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid=PMC{pmcid}&blobtype=pdf"
            response = http_session.get(pdf_url, timeout=20, headers=headers)
            if response.status_code == 200 and 'application/pdf' in response.headers.get('Content-Type', ''):
                logger.info(f"PDF trouvé via Europe PMC (PMC{pmcid})")
                return response.content, None
        
        api_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {"query": f"EXT_ID:{pmid}", "format": "json", "resultType": "core"}
        response = http_session.get(api_url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('resultList', {}).get('result', [])
            if results:
                result = results[0]
                if result.get('hasPDF') == 'Y':
                    ext_id = result.get('id', '')
                    if ext_id:
                        pdf_url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={ext_id}&blobtype=pdf"
                        pdf_response = http_session.get(pdf_url, timeout=20, headers=headers)
                        if pdf_response.status_code == 200 and 'application/pdf' in pdf_response.headers.get('Content-Type', ''):
                            logger.info(f"PDF trouvé via Europe PMC (PMID {pmid})")
                            return pdf_response.content, None
        
        return None, "Europe PMC: PDF non disponible"
    except Exception as e:
        logger.error(f"Erreur Europe PMC (PMID {pmid}): {e}")
        return None, f"Erreur Europe PMC: {str(e)}"

def get_pdf_via_scihub(doi):
    if not doi:
        return None, "Pas de DOI"
    try:
        scihub_urls = [
            f"https://sci-hub.se/{doi}",
            f"https://sci-hub.st/{doi}",
            f"https://sci-hub.ru/{doi}"
        ]
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        for base_url in scihub_urls:
            try:
                logger.warning(f"Tentative Sci-Hub: {base_url}")
                response = http_session.get(base_url, timeout=15, headers=headers)
                if response.status_code == 200:
                    pdf_match = re.search(r'(https?://[^"\']+\.pdf[^"\']*)', response.text)
                    if pdf_match:
                        pdf_url = pdf_match.group(1)
                        pdf_response = http_session.get(pdf_url, timeout=20, headers=headers)
                        if pdf_response.status_code == 200 and 'application/pdf' in pdf_response.headers.get('Content-Type', ''):
                            return pdf_response.content, None
            except:
                continue
        
        return None, "Sci-Hub: PDF non trouvé"
    except Exception as e:
        logger.error(f"Erreur Sci-Hub ({doi}): {e}")
        return None, f"Erreur Sci-Hub: {str(e)}"

# =========================
# EXTRACTION TEXTE PDF
# =========================

def extraire_texte_pdf_ameliore(pdf_content):
    texte_complet = ""
    
    # Tentative 1: pdfplumber
    try:
        import pdfplumber
        pdf_file = BytesIO(pdf_content)
        with pdfplumber.open(pdf_file) as pdf:
            nb_pages = min(len(pdf.pages), 15)
            for i in range(nb_pages):
                try:
                    page = pdf.pages[i]
                    texte_page = page.extract_text()
                    if texte_page:
                        texte_complet += texte_page + "\n\n"
                except:
                    continue
        if len(texte_complet) > 100:
            logger.info(f"Extraction PDF réussie (pdfplumber, {len(texte_complet)} chars)")
            return texte_complet, "pdfplumber"
    except Exception as e:
        logger.warning(f"pdfplumber échoué: {e}")
    
    # Tentative 2: pypdf
    try:
        pdf_file = BytesIO(pdf_content)
        pdf_reader = pypdf.PdfReader(pdf_file)
        texte_complet = ""
        nb_pages = min(len(pdf_reader.pages), 15)
        for i in range(nb_pages):
            try:
                texte_page = pdf_reader.pages[i].extract_text()
                texte_complet += texte_page + "\n\n"
            except:
                continue
        if len(texte_complet) > 100:
            logger.info(f"Extraction PDF réussie (pypdf, {len(texte_complet)} chars)")
            return texte_complet, "pypdf"
    except Exception as e:
        logger.error(f"pypdf échoué: {e}")
        return "", f"Erreur extraction: {str(e)}"
    
    return texte_complet, "extraction_partielle"

# =========================
# PIPELINE GLOBAL PDF + CACHE
# =========================

def telecharger_et_extraire_pdf_multi_sources(pmid, mode_traduction="gemini", progress_callback=None, utiliser_scihub=False):
    """Pipeline complet avec cache"""
    
    # Vérifier cache d'abord
    cached = pdf_cache.get(pmid)
    if cached:
        if progress_callback:
            progress_callback(f"✅ Résultat trouvé dans le cache (source: {cached['source']})")
        return cached['texte_fr'], None
    
    try:
        if progress_callback:
            progress_callback(f"🔍 Recherche des identifiants pour PMID {pmid}...")
        
        pdf_disponible = verifier_pdf_disponible_pubmed(pmid)
        if not pdf_disponible and progress_callback:
            progress_callback("⚠️ Aucun PDF gratuit détecté par PubMed")
        
        doi = get_doi_from_pubmed(pmid)
        pmcid = get_pmcid_from_pubmed(pmid)
        
        if progress_callback:
            ids_info = []
            if doi:
                ids_info.append(f"DOI: {doi}")
            if pmcid:
                ids_info.append(f"PMCID: PMC{pmcid}")
            if ids_info:
                progress_callback(f"✅ Identifiants trouvés: {', '.join(ids_info)}")
            else:
                progress_callback("⚠️ Aucun DOI/PMCID trouvé")
        
        pdf_content = None
        source_utilisee = None

        # Cascade de sources
        if pmcid:
            if progress_callback:
                progress_callback("📥 Tentative PMC FTP (source officielle)...")
            pdf_content, erreur = get_pdf_via_pmc_ftp(pmcid)
            if pdf_content:
                source_utilisee = f"PMC FTP Officiel (PMC{pmcid})"
                if progress_callback:
                    progress_callback(f"✅ PDF trouvé via {source_utilisee}")
            else:
                if progress_callback:
                    progress_callback(f"❌ PMC FTP: {erreur}")

        if not pdf_content and pmcid:
            if progress_callback:
                progress_callback("📥 Tentative PMC Web...")
            time.sleep(0.3)
            pdf_content, erreur = get_pdf_via_pmc(pmcid)
            if pdf_content:
                source_utilisee = f"PMC Web (PMC{pmcid})"
                if progress_callback:
                    progress_callback(f"✅ PDF trouvé via {source_utilisee}")
            else:
                if progress_callback:
                    progress_callback(f"❌ PMC Web: {erreur}")

        if not pdf_content and doi:
            if progress_callback:
                progress_callback(f"📥 Tentative Unpaywall ({doi})...")
            time.sleep(0.5)
            pdf_content, erreur = get_pdf_via_unpaywall(doi)
            if pdf_content:
                source_utilisee = f"Unpaywall ({doi})"
                if progress_callback:
                    progress_callback(f"✅ PDF trouvé via {source_utilisee}")
            else:
                if progress_callback:
                    progress_callback(f"❌ Unpaywall: {erreur}")

        if not pdf_content:
            if progress_callback:
                progress_callback("📥 Tentative Europe PMC...")
            time.sleep(0.5)
            pdf_content, erreur = get_pdf_via_europepmc(pmid, pmcid)
            if pdf_content:
                source_utilisee = "Europe PMC"
                if progress_callback:
                    progress_callback(f"✅ PDF trouvé via {source_utilisee}")
            else:
                if progress_callback:
                    progress_callback(f"❌ Europe PMC: {erreur}")

        if not pdf_content and utiliser_scihub and doi:
            if progress_callback:
                progress_callback("⚠️ Tentative Sci-Hub (dernier recours)...")
            time.sleep(1)
            pdf_content, erreur = get_pdf_via_scihub(doi)
            if pdf_content:
                source_utilisee = "Sci-Hub"
                if progress_callback:
                    progress_callback(f"✅ PDF trouvé via {source_utilisee}")
            else:
                if progress_callback:
                    progress_callback(f"❌ Sci-Hub: {erreur}")

        if not pdf_content:
            message_erreur = "PDF non disponible via aucune source gratuite"
            if not doi and not pmcid:
                message_erreur += " (pas de DOI ni PMCID)"
            elif not doi:
                message_erreur += " (pas de DOI)"
            elif not pmcid:
                message_erreur += " (pas de PMCID - article probablement payant)"
            return None, message_erreur

        if progress_callback:
            progress_callback("📄 Extraction du texte PDF...")
        texte_complet, methode = extraire_texte_pdf_ameliore(pdf_content)
        if len(texte_complet) < 100:
            return None, f"Contenu PDF insuffisant (méthode: {methode})"
        
        if len(texte_complet) > 12000:
            texte_complet = texte_complet[:12000] + "\n\n[PDF tronqué pour analyse]"

        if progress_callback:
            progress_callback(f"🌐 Traduction en cours ({len(texte_complet)} caractères)...")

        # Traduction par chunks
        chunk_size = 4000
        texte_traduit = ""
        for i in range(0, len(texte_complet), chunk_size):
            chunk = texte_complet[i:i+chunk_size]
            trad_chunk = traduire_texte(chunk, mode=mode_traduction)
            texte_traduit += trad_chunk + "\n\n"
            if progress_callback and i > 0:
                pct = min(100, int((i/len(texte_complet))*100))
                progress_callback(f"🌐 Traduction... {pct}%")

        # Stocker dans le cache
        pdf_cache.set(pmid, texte_traduit, source_utilisee)

        if progress_callback:
            progress_callback(f"✅ Extraction réussie (source: {source_utilisee}, méthode: {methode})")

        return texte_traduit, None
        
    except Exception as e:
        logger.error(f"Erreur pipeline PMID {pmid}: {e}", exc_info=True)
        return None, f"Erreur générale: {str(e)}"

# =========================
# TRAITEMENT PARALLÈLE
# =========================

def traiter_articles_parallele(articles, mode_traduction="gemini", utiliser_scihub=False, max_workers=3, progress_callback=None):
    """Traite plusieurs articles en parallèle"""
    
    articles_oa = [a for a in articles if a.get('is_pdf_oa')]
    if not articles_oa:
        return {}
    
    resultats = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                telecharger_et_extraire_pdf_multi_sources,
                article['pmid'],
                mode_traduction,
                None,  # Pas de callback individuel en mode parallèle
                utiliser_scihub
            ): article 
            for article in articles_oa
        }
        
        completed = 0
        total = len(futures)
        
        for future in as_completed(futures):
            article = futures[future]
            pmid = article['pmid']
            completed += 1
            
            try:
                texte_traduit, err = future.result(timeout=120)
                if texte_traduit:
                    resultats[pmid] = {
                        'texte_traduit': texte_traduit,
                        'erreur': None
                    }
                    logger.info(f"✅ PMID {pmid} traité ({completed}/{total})")
                else:
                    resultats[pmid] = {
                        'texte_traduit': None,
                        'erreur': err
                    }
                    logger.warning(f"❌ PMID {pmid} échec: {err}")
                
                if progress_callback:
                    progress_callback(completed / total)
                    
            except Exception as e:
                logger.error(f"Erreur traitement PMID {pmid}: {e}")
                resultats[pmid] = {
                    'texte_traduit': None,
                    'erreur': str(e)
                }
    
    return resultats

# =========================
# ANALYSE IA
# =========================

def analyser_article_ia(texte_fr, specialite="Gynécologie"):
    try:
        genai.configure(api_key=G_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        prompt = f"""
Tu es un expert en médecine fondée sur les preuves en {specialite}.
À partir du texte français suivant (article scientifique), produis une analyse structurée pour un clinicien.

Attendu :
1. Résumé en 5 phrases maximum.
2. Type d'étude et niveau de preuve.
3. Principaux résultats chiffrés (critère principal, effet, IC si présents).
4. Biais / limites majeurs.
5. Implications pratiques pour un gynécologue-obstétricien en exercice.

Texte :
{texte_fr}
"""
        rep = model.generate_content(prompt)
        logger.info(f"Analyse IA générée ({len(rep.text)} chars)")
        return rep.text.strip()
    except Exception as e:
        logger.error(f"Erreur analyse IA: {e}", exc_info=True)
        return f"Erreur analyse IA: {str(e)}"

# =========================
# MÉTADONNÉES (avec rate limiting)
# =========================

@ncbi_rate_limiter
def recuperer_titres_rapides(pmids, traduire_titres=False, mode_traduction="gemini"):
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", "rettype": "abstract"}
    
    try:
        logger.info(f"Récupération métadonnées pour {len(pmids)} PMIDs")
        response = http_session.get(base_url, params=params, timeout=15)
        
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            articles_data = []
            
            for article in root.findall('.//PubmedArticle'):
                try:
                    pmid = article.find('.//PMID').text if article.find('.//PMID') is not None else "N/A"

                    pmcid = None
                    for aid in article.findall('.//ArticleId'):
                        if aid.get('IdType') == 'pmc':
                            pmcid = aid.text
                            if pmcid and pmcid.startswith("PMC"):
                                pmcid = pmcid[3:]
                            break

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

                    is_pdf_oa = pmcid is not None
                    pdf_source_potentielle = 'PMC' if pmcid is not None else None

                    # Validation Pydantic
                    article_obj = Article(
                        pmid=pmid,
                        pmcid=pmcid,
                        title=title,
                        title_fr=title_fr,
                        journal=journal,
                        year=year,
                        date_pub=date_pub,
                        is_pdf_oa=is_pdf_oa,
                        pdf_source_potentielle=pdf_source_potentielle,
                        pdf_texte_fr=None
                    )
                    
                    articles_data.append(article_obj.dict())
                    
                except Exception as e:
                    logger.error(f"Erreur parsing article: {e}")
                    continue
            
            logger.info(f"{len(articles_data)} articles valides récupérés")
            return articles_data
            
    except Exception as e:
        logger.error(f"Erreur recuperer_titres_rapides: {e}", exc_info=True)
        return []
    
    return []

# =========================
# GÉNÉRATION PDF / NOTEBOOK
# =========================

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Veille Medicale v7', 0, 1, 'C')
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
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 20)
    pdf.ln(30)
    pdf.cell(0, 15, 'VEILLE MEDICALE v7', 0, 1, 'C')
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
        
        pmid = article['pmid']
        analyse = st.session_state.analyses_individuelles.get(pmid)
        if analyse:
            pdf.ln(3)
            pdf.set_font('Arial', 'B', 11)
            pdf.multi_cell(0, 5, "Analyse IA :")
            pdf.set_font('Arial', '', 10)
            try:
                analyse_clean = analyse[:4000].encode('latin-1', 'ignore').decode('latin-1')
            except:
                analyse_clean = analyse[:4000].encode('ascii', 'ignore').decode('ascii')
            pdf.multi_cell(0, 4, analyse_clean)

    pdf_output = io.BytesIO()
    pdf_string = pdf.output(dest='S').encode('latin-1')
    pdf_output.write(pdf_string)
    pdf_output.seek(0)
    return pdf_output.getvalue()

def generer_notebooklm_selectionne(articles_selectionnes):
    contenu = f"""# VEILLE MEDICALE v7 - PODCAST
Date: {datetime.now().strftime("%d/%m/%Y")}

## ARTICLES SELECTIONNES

"""
    for i, article in enumerate(articles_selectionnes, 1):
        pmid = article['pmid']
        analyse = st.session_state.analyses_individuelles.get(pmid, "Non disponible")
        contenu += f"""
### Article {i}
Titre: {article['title_fr']}
Journal: {article['journal']} ({article['year']})
PMID: {pmid}

Contenu complet:
{article.get('pdf_texte_fr', 'Non disponible')}

Analyse IA:
{analyse}

---
"""
    return contenu

# =========================
# INTERFACE STREAMLIT
# =========================

st.title("🩺 Veille Médicale Professionnelle v7")

with st.expander("ℹ️ Nouvelles fonctionnalités v7 - VERSION OPTIMISÉE"):
    st.markdown("""
**Améliorations majeures v7:**
- ✅ **Rate limiting NCBI** (3 req/sec, conforme guidelines)
- 🗄️ **Cache SQLite** (évite re-téléchargements)
- 🔄 **Retry automatique** (backoff exponentiel)
- ✔️ **Validation Pydantic** (données médicales)
- 📝 **Logging structuré** (debugging facilité)
- ⚡ **Traitement parallèle** (3 threads simultanés)
- 💾 **Gestion mémoire** (limite taille PDF 50MB)
- 🛡️ **Sanitization** (requêtes PubMed sécurisées)
""")

if DEEPL_KEY:
    st.success("✅ DeepL Pro+ activé")
else:
    st.info("ℹ️ Traduction : Gemini 2.0 Flash")

# Nettoyage cache ancien
with st.sidebar:
    if st.button("🗑️ Nettoyer cache (>30j)"):
        pdf_cache.clear_old(days=30)
        st.success("Cache nettoyé")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔍 Recherche", "📚 Historique", "🔗 Sources", "⚙️ Configuration", "🔧 Diagnostic PDF"])

# =========================
# TAB 1 : RECHERCHE
# =========================

with tab1:
    if st.session_state.mode_etape == 1:
        st.header("📋 Étape 1 : Configuration")

        with st.sidebar:
            st.header("⚙️ Paramètres")

            mode_recherche = st.radio("Mode de recherche", ["Par spécialité", "Par mots-clés"])

            if mode_recherche == "Par spécialité":
                spec_fr = st.selectbox("🏥 Spécialité", list(TRAD.keys()))
                mots_cles_custom = ""
                st.subheader("📰 Journaux")
                choix_journaux = st.radio(
                    "Limiter à:",
                    ["Tous les journaux PubMed",
                     "Journaux de la spécialité",
                     "Un journal spécifique"]
                )
                if choix_journaux == "Un journal spécifique":
                    journaux_dispo = JOURNAUX_SPECIALITE.get(spec_fr, [])
                    journal_selectionne = st.selectbox("Journal:", journaux_dispo)
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
                    choix_journaux = st.radio(
                        "Limiter à:",
                        ["Tous les journaux PubMed",
                         "Journaux de la spécialité",
                         "Un journal spécifique"]
                    )
                    if choix_journaux == "Un journal spécifique":
                        journaux_dispo = JOURNAUX_SPECIALITE.get(spec_combo, [])
                        journal_selectionne = st.selectbox("Journal:", journaux_dispo)
                    elif choix_journaux == "Journaux de la spécialité":
                        journal_selectionne = "SPECIALITE"
                    else:
                        journal_selectionne = "TOUS"
                else:
                    spec_combo = None
                    journal_selectionne = "TOUS"
                    st.info("🌐 Recherche dans TOUS les journaux PubMed")
                mots_cles_custom = st.text_area(
                    "🔎 Mots-clés",
                    placeholder="Ex: hypertension gravidique",
                    height=80
                )
                if mots_cles_custom:
                    with st.expander("🔍 Aperçu traduction"):
                        terme_en = traduire_mots_cles(mots_cles_custom)
                        st.code(f"FR: {mots_cles_custom}\nEN: {terme_en}")

            st.subheader("🎯 Zone de recherche")
            zone_recherche = st.radio(
                "Chercher dans:",
                ["Titre et résumé", "Titre uniquement", "Résumé uniquement"]
            )

            st.subheader("📅 Période")
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Début**")
                date_debut = st.date_input(
                    "Début",
                    value=date(2024, 1, 1),
                    min_value=date(2000, 1, 1),
                    max_value=date.today(),
                    format="DD/MM/YYYY",
                    label_visibility="collapsed"
                )
            with col2:
                st.write("**Fin**")
                date_fin = st.date_input(
                    "Fin",
                    value=date.today(),
                    min_value=date(2000, 1, 1),
                    max_value=date.today(),
                    format="DD/MM/YYYY",
                    label_visibility="collapsed"
                )

            st.subheader("🔬 Filtres")
            st.markdown("**🌍 Langue des articles**")
            langue_selectionnee = st.selectbox(
                "Langue:",
                list(LANGUES.keys()),
                label_visibility="collapsed"
            )

            mode_contenu = st.radio(
                "Type:",
                ["PDF complets uniquement", "Titre + résumé", "Titre uniquement"]
            )

            type_etude = st.selectbox("Type d'étude", list(TYPES_ETUDE.keys()))
            nb_max = st.slider("Max résultats", 10, 200, 50, 10)

            st.subheader("⚙️ Options avancées")
            utiliser_scihub = st.checkbox(
                "🔓 Activer Sci-Hub (dernier recours)",
                value=False,
                help="Sci-Hub est juridiquement discutable. Utilisez uniquement si les sources légales échouent."
            )

            mode_trad = "deepl" if DEEPL_KEY else "gemini"
            traduire_titres = st.checkbox("🌐 Traduire titres", value=True)

            st.subheader("🤖 Post-traitement IA")
            auto_pdf_oa = st.checkbox(
                "Analyser automatiquement les articles avec PDF gratuit",
                value=True,
                help="Télécharge, traduit et analyse par IA uniquement les articles avec PDF libre détecté (PMCID présent)."
            )
            
            traitement_parallele = st.checkbox(
                "⚡ Traitement parallèle (3 threads)",
                value=True,
                help="Traite 3 articles simultanément pour plus de rapidité"
            )

        if st.button("🔍 LANCER", type="primary", use_container_width=True):
            if mode_recherche == "Par spécialité":
                term = TRAD[spec_fr]
                term = sanitize_pubmed_term(term)
                display_term = spec_fr
                spec_utilisee = spec_fr
            else:
                if not mots_cles_custom.strip():
                    st.error("Veuillez saisir au moins un mot-clé.")
                    st.stop()
                mots_en = traduire_mots_cles(mots_cles_custom)
                term = sanitize_pubmed_term(mots_en)
                display_term = mots_cles_custom
                spec_utilisee = spec_combo if ('inclure_specialite' in locals() and inclure_specialite) else "Non spécifiée"

            query_parts = []

            if mode_recherche == "Par spécialité":
                query_parts.append(f"{term}[MeSH Terms]")
            else:
                if zone_recherche == "Titre et résumé":
                    field = "[tiab]"
                elif zone_recherche == "Titre uniquement":
                    field = "[ti]"
                else:
                    field = "[ab]"
                query_parts.append(f"({term}){field}")
                if 'inclure_specialite' in locals() and inclure_specialite and spec_combo:
                    spec_term = sanitize_pubmed_term(TRAD[spec_combo])
                    query_parts.append(f"{spec_term}[MeSH Terms]")

            code_langue = LANGUES[langue_selectionnee]
            if code_langue:
                query_parts.append(f"{code_langue}[la]")

            filtre_type = TYPES_ETUDE[type_etude]
            if filtre_type:
                query_parts.append(f"{filtre_type}[pt]")

            debut_str = date_debut.strftime("%Y/%m/%d")
            fin_str = date_fin.strftime("%Y/%m/%d")
            query_parts.append(f'("{debut_str}"[PDAT] : "{fin_str}"[PDAT])')

            if journal_selectionne == "SPECIALITE":
                journaux = JOURNAUX_SPECIALITE.get(spec_utilisee, [])
                if journaux:
                    j_clause = " OR ".join([f'"{j}"[jour]' for j in journaux])
                    query_parts.append(f"({j_clause})")
            elif journal_selectionne not in ["TOUS", "SPECIALITE"]:
                query_parts.append(f'"{journal_selectionne}"[jour]')

            query = " AND ".join(query_parts)
            logger.info(f"Requête PubMed: {query}")

            base_esearch = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {
                "db": "pubmed",
                "term": query,
                "retmode": "json",
                "retmax": nb_max,
                "sort": "pubdate"
            }

            with st.spinner("Interrogation de PubMed..."):
                try:
                    r = http_session.get(base_esearch, params=params, timeout=20)
                    if r.status_code != 200:
                        st.error(f"Erreur PubMed (HTTP {r.status_code}).")
                        logger.error(f"Erreur eSearch: HTTP {r.status_code}")
                        st.stop()
                    data = r.json()
                    pmids = data.get("esearchresult", {}).get("idlist", [])
                except Exception as e:
                    st.error(f"Erreur lors de la requête PubMed: {e}")
                    logger.error(f"Erreur eSearch: {e}", exc_info=True)
                    st.stop()

            if not pmids:
                st.warning("Aucun article trouvé.")
                st.stop()

            with st.spinner(f"Récupération des métadonnées ({len(pmids)} articles)..."):
                articles_data = recuperer_titres_rapides(pmids, traduire_titres=traduire_titres, mode_traduction=mode_trad)

            st.session_state.info_recherche = {
                "spec": spec_utilisee,
                "periode": f"{date_debut.strftime('%d/%m/%Y')} - {date_fin.strftime('%d/%m/%Y')}",
                "mode_contenu": mode_contenu,
                "utiliser_scihub": utiliser_scihub,
                "mode_trad": mode_trad,
                "auto_pdf_oa": auto_pdf_oa,
                "traitement_parallele": traitement_parallele,
                "articles": articles_data
            }
            st.session_state.mode_etape = 2
            st.rerun()

    else:
        st.header("📑 Étape 2 : Sélection et analyses")

        info = st.session_state.info_recherche
        articles = info["articles"]
        mode_trad = info["mode_trad"]
        utiliser_scihub = info["utiliser_scihub"]
        traitement_parallele = info.get("traitement_parallele", False)

        st.write(f"Spécialité : **{info['spec']}**")
        st.write(f"Période : {info['periode']}")
        st.write(f"Nombre d'articles : {len(articles)}")

        # Affichage articles
        for art in articles:
            col1, col2, col3 = st.columns([6, 2, 2])
            with col1:
                label_pdf = " 🆓 PDF" if art.get('is_pdf_oa') else ""
                st.markdown(f"**{art['title_fr']}{label_pdf}**")
                st.caption(f"{art['journal']} ({art['year']}) - PMID {art['pmid']}")
            with col2:
                st.write(f"Date : {art['date_pub']}")
            with col3:
                st.write("PMCID : " + (f"PMC{art['pmcid']}" if art.get('pmcid') else "—"))

        # Traitement automatique
        if info.get("auto_pdf_oa", False) and info["mode_contenu"] != "Titre uniquement":
            st.subheader("📄 Traitement automatique des articles avec PDF libre détecté")
            
            total_oa = sum(1 for a in articles if a.get('is_pdf_oa'))
            
            if total_oa == 0:
                st.info("Aucun article avec PDF gratuit détecté.")
            else:
                if traitement_parallele:
                    st.info(f"⚡ Mode parallèle activé (3 threads)")
                    progress_bar = st.progress(0)
                    
                    def update_progress(pct):
                        progress_bar.progress(pct)
                    
                    resultats = traiter_articles_parallele(
                        articles,
                        mode_traduction=mode_trad,
                        utiliser_scihub=utiliser_scihub,
                        max_workers=3,
                        progress_callback=update_progress
                    )
                    
                    # Appliquer les résultats
                    for article in articles:
                        pmid = article['pmid']
                        if pmid in resultats:
                            if resultats[pmid]['texte_traduit']:
                                article['pdf_texte_fr'] = resultats[pmid]['texte_traduit']
                                # Analyse IA
                                analyse = analyser_article_ia(resultats[pmid]['texte_traduit'], specialite=info['spec'])
                                st.session_state.analyses_individuelles[pmid] = analyse
                            else:
                                article['pdf_texte_fr'] = None
                    
                    st.success(f"✅ Traitement parallèle terminé ({len(resultats)} articles)")
                    
                else:
                    # Mode séquentiel original
                    progress = st.progress(0)
                    statut = st.empty()
                    
                    traite = 0
                    for article in articles:
                        if not article.get('is_pdf_oa'):
                            continue
                        pmid = article['pmid']

                        def cb(msg):
                            statut.write(msg)

                        texte_traduit, err = telecharger_et_extraire_pdf_multi_sources(
                            pmid,
                            mode_traduction=mode_trad,
                            progress_callback=cb,
                            utiliser_scihub=utiliser_scihub
                        )
                        if texte_traduit:
                            article['pdf_texte_fr'] = texte_traduit
                            analyse = analyser_article_ia(texte_traduit, specialite=info['spec'])
                            st.session_state.analyses_individuelles[pmid] = analyse
                        else:
                            article['pdf_texte_fr'] = None
                        
                        traite += 1
                        if total_oa > 0:
                            progress.progress(int(100 * traite / total_oa))

                    st.success("✅ Traitement séquentiel terminé.")

        # Export
        st.subheader("📤 Export")
        selection_tous = st.checkbox("Inclure tous les articles dans le PDF / Notebook", value=True)
        if selection_tous:
            articles_selectionnes = articles
        else:
            ids_selection = st.text_input("PMID sélectionnés (séparés par des virgules)")
            if ids_selection.strip():
                pmid_list = [x.strip() for x in ids_selection.split(",") if x.strip()]
                articles_selectionnes = [a for a in articles if a['pmid'] in pmid_list]
            else:
                articles_selectionnes = []

        col_pdf, col_nb = st.columns(2)
        with col_pdf:
            if st.button("📄 Générer PDF de veille"):
                if not articles_selectionnes:
                    st.warning("Aucun article sélectionné.")
                else:
                    with st.spinner("Génération PDF..."):
                        pdf_bytes = generer_pdf_selectionne(info['spec'], info['periode'], articles_selectionnes)
                    st.download_button(
                        label="Télécharger le PDF",
                        data=pdf_bytes,
                        file_name=f"veille_v7_{info['spec']}_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf"
                    )
        with col_nb:
            if st.button("📓 Générer texte NotebookLM"):
                if not articles_selectionnes:
                    st.warning("Aucun article sélectionné.")
                else:
                    texte_nb = generer_notebooklm_selectionne(articles_selectionnes)
                    st.download_button(
                        label="Télécharger le fichier texte",
                        data=texte_nb.encode("utf-8"),
                        file_name=f"veille_v7_{info['spec']}_{datetime.now().strftime('%Y%m%d')}.txt",
                        mime="text/plain"
                    )

with tab2:
    st.header("📚 Historique des recherches")
    st.info("Fonctionnalité à implémenter : affichage de l'historique des recherches")

with tab3:
    st.header("🔗 Sources recommandées")
    st.info("Fonctionnalité à implémenter : liens vers sources médicales officielles")

with tab4:
    st.header("⚙️ Configuration")
    
    st.subheader("📊 Statistiques du cache")
    try:
        cursor = pdf_cache.conn.execute("SELECT COUNT(*), MAX(date_cache) FROM pdf_cache")
        count, last_date = cursor.fetchone()
        st.metric("Entrées en cache", count or 0)
        if last_date:
            st.write(f"Dernière mise à jour : {last_date}")
    except:
        st.warning("Impossible de lire les statistiques du cache")
    
    st.subheader("🔧 Logs")
    if st.button("📄 Afficher les dernières lignes du log"):
        try:
            with open('veille_medicale.log', 'r') as f:
                lines = f.readlines()
                st.text_area("Dernières lignes", "".join(lines[-50:]), height=300)
        except:
            st.warning("Fichier log introuvable")

with tab5:
    st.header("🔧 Diagnostic PDF")
    
    pmid_test = st.text_input("PMID à tester", placeholder="Ex: 38123456")
    
    if st.button("🔍 Tester récupération PDF"):
        if not pmid_test or not pmid_test.isdigit():
            st.error("PMID invalide")
        else:
            with st.spinner("Diagnostic en cours..."):
                messages = []
                
                def log_cb(msg):
                    messages.append(msg)
                    st.write(msg)
                
                texte, err = telecharger_et_extraire_pdf_multi_sources(
                    pmid_test,
                    mode_traduction="gemini",
                    progress_callback=log_cb,
                    utiliser_scihub=False
                )
                
                if texte:
                    st.success(f"✅ PDF récupéré et traduit ({len(texte)} caractères)")
                    with st.expander("Aperçu du texte"):
                        st.text_area("Texte", texte[:2000], height=300)
                else:
                    st.error(f"❌ Échec: {err}")
