# ============================================
# PARTIE 1 — IMPORTS & CONFIGURATION GÉNÉRALE
# ============================================

import streamlit as st
from datetime import date
import locale
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import google.generativeai as genai
import tarfile
from io import BytesIO
import pypdf
import base64
from reportlab.lib.pagesizes import A4        # <-- NEW
from reportlab.pdfgen import canvas          # <-- NEW
import anthropic


# Locale FR pour les dates
try:
    locale.setlocale(locale.LC_TIME, "fr_FR.UTF-8")
except Exception:
    pass

# Configuration Streamlit
st.set_page_config(
    page_title="Veille Médicale Pro",
    page_icon="🩺",
    layout="wide"
)

st.title("🩺 Veille Médicale Professionnelle")

# Récupération des clés avec debug
try:
    G_KEY = st.secrets["GEMINI_KEY"]
    st.sidebar.success("✅ Clé Gemini chargée")
except Exception as e:
    st.error(f"⚠️ Clé GEMINI_KEY manquante dans st.secrets: {e}")
    st.stop()

# Clé Claude (optionnelle)
try:
    CLAUDE_KEY = st.secrets["CLAUDE_KEY"]
    client_claude = anthropic.Anthropic(api_key=CLAUDE_KEY)
    st.sidebar.success("✅ Clé Claude chargée")
except Exception:
    client_claude = None
    st.sidebar.info("ℹ️ Claude non configuré")

# Clé DeepL (optionnelle)
DEEPL_KEY = st.secrets.get("DEEPL_KEY", None)
if DEEPL_KEY:
    st.sidebar.success("✅ Clé DeepL chargée")
else:
    st.sidebar.info("ℹ️ DeepL non configuré, utilisation de Gemini")

# Email Unpaywall
UNPAYWALL_EMAIL = st.secrets.get("UNPAYWALL_EMAIL", "example@email.com")

# Mode de traduction par défaut
MODE_TRAD = "deepl" if DEEPL_KEY else "gemini"

# Session state
if "articles" not in st.session_state:
    st.session_state.articles = []
if "details" not in st.session_state:
    st.session_state.details = {}
if "historique" not in st.session_state:
    st.session_state.historique = []
if "debug" not in st.session_state:
    st.session_state.debug = True  # Activé par défaut pour debug


# ============================================
# CONFIGURATION DES SPÉCIALITÉS
# ============================================

SPECIALITES = {
    "Anesthésie Réanimation": {
        "journaux": [
            "Anesthesiology",
            "British Journal of Anaesthesia",
            "Anaesthesia",
            "Critical Care Medicine",
            "Intensive Care Medicine"
        ],
        "mesh_terms": "Anesthesiology[MeSH Terms] OR Critical Care[MeSH Terms] OR Intensive Care[MeSH Terms]"
    },
    "Cardiologie": {
        "journaux": [
            "Circulation",
            "European Heart Journal",
            "Journal of the American College of Cardiology",
            "Hypertension",
            "Heart"
        ],
        "mesh_terms": "Cardiology[MeSH Terms] OR Cardiovascular Diseases[MeSH Terms]"
    },
    "Chirurgie Orthopédique": {
        "journaux": [
            "The Journal of Bone and Joint Surgery",
            "Journal of Orthopaedic Research",
            "Clinical Orthopaedics and Related Research",
            "Arthroscopy"
        ],
        "mesh_terms": "Orthopedics[MeSH Terms] OR Orthopedic Procedures[MeSH Terms]"
    },
    "Chirurgie Viscérale": {
        "journaux": [
            "Annals of Surgery",
            "British Journal of Surgery",
            "JAMA Surgery",
            "Journal of the American College of Surgeons"
        ],
        "mesh_terms": "General Surgery[MeSH Terms] OR Digestive System Surgical Procedures[MeSH Terms]"
    },
    "Endocrinologie": {
        "journaux": [
            "Journal of Clinical Endocrinology & Metabolism",
            "Diabetes Care",
            "Diabetologia",
            "Thyroid"
        ],
        "mesh_terms": "Endocrinology[MeSH Terms] OR Endocrine System Diseases[MeSH Terms]"
    },
    "Gynécologie / Obstétrique": {
        "journaux": [
            "Obstetrics and Gynecology",
            "American Journal of Obstetrics and Gynecology",
            "BJOG",
            "Human Reproduction"
        ],
        "mesh_terms": "Gynecology[MeSH Terms] OR Obstetrics[MeSH Terms]"
    },
    "Hématologie": {
        "journaux": [
            "Blood",
            "Haematologica",
            "Leukemia",
            "Journal of Thrombosis and Haemostasis"
        ],
        "mesh_terms": "Hematology[MeSH Terms] OR Hematologic Diseases[MeSH Terms]"
    },
    "Hépato-Gastro-Entérologie": {
        "journaux": [
            "Gastroenterology",
            "Gut",
            "Hepatology",
            "American Journal of Gastroenterology",
            "Journal of Hepatology"
        ],
        "mesh_terms": "Gastroenterology[MeSH Terms] OR Gastrointestinal Diseases[MeSH Terms] OR Liver Diseases[MeSH Terms]"
    },
    "Infectiologie": {
        "journaux": [
            "The Lancet Infectious Diseases",
            "Clinical Infectious Diseases",
            "The Journal of Infectious Diseases",
            "Emerging Infectious Diseases"
        ],
        "mesh_terms": "Infectious Diseases[MeSH Terms] OR Communicable Diseases[MeSH Terms]"
    },
    "Médecine Générale": {
        "journaux": [
            "The BMJ",
            "JAMA",
            "The Lancet",
            "Annals of Family Medicine",
            "British Journal of General Practice"
        ],
        "mesh_terms": "General Practice[MeSH Terms] OR Family Practice[MeSH Terms] OR Primary Health Care[MeSH Terms]"
    },
    "Médecine Interne": {
        "journaux": [
            "Annals of Internal Medicine",
            "JAMA Internal Medicine",
            "The American Journal of Medicine",
            "Archives of Internal Medicine"
        ],
        "mesh_terms": "Internal Medicine[MeSH Terms]"
    },
    "Néphrologie": {
        "journaux": [
            "Journal of the American Society of Nephrology",
            "Kidney International",
            "Nephrology Dialysis Transplantation"
        ],
        "mesh_terms": "Nephrology[MeSH Terms] OR Kidney Diseases[MeSH Terms]"
    },
    "Neurologie": {
        "journaux": [
            "Neurology",
            "Brain",
            "Annals of Neurology",
            "Stroke"
        ],
        "mesh_terms": "Neurology[MeSH Terms] OR Nervous System Diseases[MeSH Terms]"
    },
    "Oncologie": {
        "journaux": [
            "Journal of Clinical Oncology",
            "Cancer",
            "The Lancet Oncology",
            "Annals of Oncology"
        ],
        "mesh_terms": "Oncology[MeSH Terms] OR Neoplasms[MeSH Terms]"
    },
    "ORL": {
        "journaux": [
            "The Laryngoscope",
            "Otolaryngology--Head and Neck Surgery",
            "International Forum of Allergy & Rhinology",
            "JAMA Otolaryngology–Head & Neck Surgery"
        ],
        "mesh_terms": "Otolaryngology[MeSH Terms] OR Otorhinolaryngologic Diseases[MeSH Terms]"
    },
    "Pédiatrie": {
        "journaux": [
            "Pediatrics",
            "JAMA Pediatrics",
            "The Journal of Pediatrics",
            "Archives of Disease in Childhood"
        ],
        "mesh_terms": "Pediatrics[MeSH Terms] OR Child[MeSH Terms]"
    },
    "Pneumologie": {
        "journaux": [
            "American Journal of Respiratory and Critical Care Medicine",
            "Chest",
            "Thorax",
            "European Respiratory Journal"
        ],
        "mesh_terms": "Pulmonary Medicine[MeSH Terms] OR Respiratory Tract Diseases[MeSH Terms]"
    },
    "Psychiatrie": {
        "journaux": [
            "American Journal of Psychiatry",
            "JAMA Psychiatry",
            "The Lancet Psychiatry",
            "Biological Psychiatry"
        ],
        "mesh_terms": "Psychiatry[MeSH Terms] OR Mental Disorders[MeSH Terms]"
    },
    "Urologie": {
        "journaux": [
            "The Journal of Urology",
            "European Urology",
            "BJU International",
            "Urology"
        ],
        "mesh_terms": "Urology[MeSH Terms] OR Urologic Diseases[MeSH Terms]"
    }
}


# ============================================
# PARTIE 2 — FONCTIONS UTILITAIRES TEXTE
# ============================================

def nettoyer_titre(titre: str) -> str:
    """Nettoie le titre d'article : balises HTML, mentions 'see more', espaces."""
    if not titre:
        return "Titre non disponible"

    titre = re.sub(r'<[^>]+>', '', titre)
    patterns = [
        r'\s*see\s+more\s*',
        r'\[see\s+more\]',
        r'\(see\s+more\)',
        r'\(\s*see\s+more\s*\)',
        r'\s*voir\s+plus\s*',
        r'\[voir\s+plus\]',
        r'\(voir\s+plus\)',
    ]

    for pat in patterns:
        titre = re.sub(pat, '', titre, flags=re.IGNORECASE)

    titre = re.sub(r'\s+', ' ', titre)
    return titre.strip()


def nettoyer_abstract(texte: str) -> str:
    """Nettoie un abstract : supprime balises, espaces, artefacts."""
    if not texte:
        return ""

    texte = re.sub(r'<[^>]+>', '', texte)
    texte = re.sub(r'^[A-Z ]{3,20}:\s*', '', texte)
    texte = re.sub(r'\s+', ' ', texte)

    return texte.strip()


def nettoyer_texte_pdf(texte: str) -> str:
    """Nettoyage avancé du texte extrait des PDF."""
    if not texte:
        return ""

    texte = texte.replace('\x00', ' ')
    texte = re.sub(r'\s+', ' ', texte)

    artefacts = [
        r'Received\s+\d{4}',
        r'Accepted\s+\d{4}',
        r'©\s*\d{4}',
        r'All rights reserved',
        r'This article is protected by copyright',
    ]

    for pat in artefacts:
        texte = re.sub(pat, '', texte, flags=re.IGNORECASE)

    return texte.strip()


def tronquer(texte: str, max_len: int = 12000) -> str:
    """Tronque un texte trop long pour éviter surcharge de traduction."""
    if not texte:
        return texte
    if len(texte) <= max_len:
        return texte
    return texte[:max_len] + "\n\n[Texte tronqué pour analyse]"


def maintenant_str() -> str:
    """Retourne la date/heure actuelle au format français."""
    return datetime.now().strftime("%d/%m/%Y %H:%M")


# ============================================
# PARTIE 3 — TRADUCTION (DEEPL / GEMINI / CLAUDE)
# ============================================

def traduire_deepl_chunk(texte: str, api_key: str) -> str:
    """Traduit un chunk de texte via DeepL."""
    url = "https://api-free.deepl.com/v2/translate"
    data = {
        "auth_key": api_key,
        "text": texte,
        "target_lang": "FR",
        "source_lang": "EN",
        "formality": "more"
    }
    r = requests.post(url, data=data, timeout=40)
    r.raise_for_status()
    return r.json()["translations"][0]["text"]


def traduire_gemini_chunk(texte: str, g_key: str) -> str:
    """Traduit un chunk de texte via Gemini."""
    try:
        genai.configure(api_key=g_key)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")

        prompt = f"""Tu es un traducteur médical professionnel. Traduis le texte anglais suivant en français médical professionnel.

CONSIGNES STRICTES:
- Fournis UNIQUEMENT la traduction française
- Pas de préambule
- Pas de numérotation
- Conserve la terminologie médicale exacte

TEXTE À TRADUIRE:
{texte}

TRADUCTION FRANÇAISE:"""

        resp = model.generate_content(prompt)

        if not resp or not hasattr(resp, 'text'):
            return texte

        trad = resp.text.strip()
        trad = trad.replace("**", "")
        trad = re.sub(r'^(Traduction\s*:?\s*)', '', trad, flags=re.IGNORECASE)
        return trad.strip()

    except Exception as e:
        st.error(f"❌ Erreur traduction Gemini: {e}")
        return texte


def traduire_claude(texte: str) -> str:
    """Traduction FR via Claude (fallback)."""
    if not client_claude:
        return texte

    try:
        msg = client_claude.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": f"Traduis ce texte en français médical professionnel, sans préambule :\n\n{texte}"
                }
            ]
        )
        return msg.content[0].text.strip()
    except Exception:
        return texte


def traduire_avec_fallback(texte: str) -> str:
    """Tente Gemini, puis Claude si erreur."""
    try:
        return traduire_gemini_chunk(texte, G_KEY)
    except Exception:
        return traduire_claude(texte)


@st.cache_data(show_spinner=False)
def traduire_long_texte_cache(
    texte: str,
    mode: str,
    deepl_key: str = None,
    g_key: str = None,
    chunk_size: int = 4000
) -> str:
    """Traduit un texte long en le découpant automatiquement."""
    texte = texte.strip()
    if not texte:
        return texte

    chunks = [texte[i:i+chunk_size] for i in range(0, len(texte), chunk_size)]
    trad_total = []

    for chunk in chunks:
        try:
            if mode == "deepl" and deepl_key:
                t = traduire_deepl_chunk(chunk, deepl_key)
            else:
                t = traduire_avec_fallback(chunk)
            trad_total.append(t)
        except Exception as e:
            st.error(f"❌ Erreur traduction chunk: {e}")
            trad_total.append(chunk)

    return "\n\n".join(trad_total)


def traduire_texte_court_cache(
    texte: str,
    mode: str,
    deepl_key: str = None,
    g_key: str = None
) -> str:
    """Traduit un texte court (titre, phrase)."""
    texte = texte.strip()
    if not texte:
        return texte

    if mode == "deepl" and deepl_key:
        return traduire_deepl_chunk(texte, deepl_key)
    else:
        return traduire_avec_fallback(texte)


def traduire_mots_cles_gemini(mots_cles_fr: str, g_key: str) -> str:
    """Traduit des mots-clés FR → EN optimisés pour PubMed (MeSH si possible)."""
    try:
        genai.configure(api_key=g_key)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")

        prompt = f"""Tu es un expert en terminologie médicale. Traduis ces mots-clés français en termes médicaux anglais optimisés pour PubMed.

CONSIGNES:
- Fournis UNIQUEMENT les termes anglais
- Utilise la terminologie MeSH quand possible
- Sépare les termes par des virgules

MOTS-CLÉS FRANÇAIS:
{mots_cles_fr}

TERMES ANGLAIS:"""

        resp = model.generate_content(prompt)
        return resp.text.strip()
    except Exception as e:
        st.error(f"❌ Erreur traduction mots-clés: {e}")
        return mots_cles_fr


def resumer_claude(texte: str, mode="court") -> str:
    """Résumé FR via Claude."""
    if not client_claude:
        return texte

    consignes = (
        "Résumé très court (3–5 lignes), style professionnel."
        if mode == "court"
        else "Résumé détaillé, structuré, style fiche de lecture."
    )

    try:
        msg = client_claude.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=2500,
            messages=[
                {
                    "role": "user",
                    "content": f"{consignes}\n\nTEXTE :\n{texte}"
                }
            ]
        )
        return msg.content[0].text.strip()
    except Exception:
        return texte


def resumer_avec_fallback(texte: str, mode="court") -> str:
    """Résumé via Gemini, fallback Claude."""
    try:
        genai.configure(api_key=G_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")

        prompt = f"""
        Résume ce texte en français ({mode}).

        CONSIGNES :
        - Style professionnel
        - Pas de phrases inutiles
        - Conserve les données clés

        TEXTE :
        {texte}
        """

        resp = model.generate_content(prompt)
        return resp.text.strip()

    except Exception:
        return resumer_claude(texte, mode=mode)



# ============================================
# PARTIE 4 — PUBMED : RECHERCHE & MÉTADONNÉES
# ============================================

BASE_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def construire_query_pubmed(
    base_query: str,
    date_debut,
    date_fin,
    langue_code: str = "",
    type_etude: str = ""
) -> str:
    """Construit une requête PubMed complète."""
    query = base_query.strip()

    if date_debut and date_fin:
        query += (
            f' AND ("{date_debut:%Y/%m/%d}"[Date - Publication] : '
            f'"{date_fin:%Y/%m/%d}"[Date - Publication])'
        )

    if langue_code:
        query += f' AND {langue_code}[lang]'

    if type_etude:
        query += f' AND {type_etude}[pt]'

    return query


@st.cache_data(show_spinner=False)
def pubmed_search_ids(query: str, max_results: int = 50):
    """Recherche les PMIDs correspondant à une requête PubMed."""
    try:
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json"
        }

        r = requests.get(f"{BASE_EUTILS}/esearch.fcgi", params=params, timeout=20)
        r.raise_for_status()
        data = r.json()

        return data.get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        st.error(f"❌ Erreur recherche PubMed: {e}")
        return []


@st.cache_data(show_spinner=False)
def pubmed_fetch_metadata_and_abstracts(pmids):
    """Récupère les métadonnées et abstracts pour une liste de PMIDs."""
    if not pmids:
        return []

    try:
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml"
        }

        r = requests.get(f"{BASE_EUTILS}/efetch.fcgi", params=params, timeout=30)
        r.raise_for_status()

        root = ET.fromstring(r.content)
        results = []

        for article in root.findall('.//PubmedArticle'):
            pmid_elem = article.find('.//PMID')
            pmid = pmid_elem.text if pmid_elem is not None else None

            title_elem = article.find('.//ArticleTitle')
            title = ''.join(title_elem.itertext()) if title_elem is not None else "Titre non disponible"
            title = nettoyer_titre(title)

            journal_elem = article.find('.//Journal/Title')
            journal = journal_elem.text if journal_elem is not None else "Journal non disponible"

            year_elem = article.find('.//PubDate/Year')
            year = year_elem.text if year_elem is not None else "N/A"

            doi = None
            pmcid = None
            for aid in article.findall('.//ArticleId'):
                if aid.get('IdType') == 'doi':
                    doi = aid.text
                if aid.get('IdType') == 'pmc':
                    pmcid = aid.text

            abstract_texts = []
            for abst in article.findall('.//Abstract/AbstractText'):
                part = ''.join(abst.itertext())
                if part:
                    abstract_texts.append(part.strip())

            abstract = nettoyer_abstract("\n\n".join(abstract_texts))

            results.append({
                "pmid": pmid,
                "title_en": title,
                "journal": journal,
                "year": year,
                "doi": doi,
                "pmcid": pmcid,
                "abstract_en": abstract
            })

        return results
    except Exception as e:
        st.error(f"❌ Erreur récupération métadonnées: {e}")
        return []


# ============================================
# PARTIE 5 — PDF : RÉCUPÉRATION & EXTRACTION
# ============================================

def _clean_pmcid(pmcid: str) -> str:
    """Nettoie le PMCID en enlevant le préfixe PMC s'il existe."""
    if not pmcid:
        return ""
    return pmcid.replace("PMC", "").strip()

def check_pdf_free_unpaywall(doi, email):
    """Vérifie via Unpaywall si un PDF OA est disponible, sans forcément le télécharger."""
    if not doi:
        return False, None, "Pas de DOI"

    try:
        url = f"https://api.unpaywall.org/v2/{doi}"
        params = {"email": email}
        r = requests.get(url, params=params, timeout=20)

        if r.status_code == 404:
            return False, None, "Unpaywall: DOI inconnu"
        if r.status_code != 200:
            return False, None, f"Unpaywall HTTP {r.status_code}"

        data = r.json()

        if not data.get("is_oa"):
            return False, None, "Unpaywall: pas Open Access"

        # On privilégie best_oa_location
        best = data.get("best_oa_location")
        if best and best.get("url_for_pdf"):
            return True, best["url_for_pdf"], None

        # Sinon on regarde dans oa_locations
        for loc in data.get("oa_locations", []):
            pdf_url = loc.get("url_for_pdf")
            if pdf_url:
                return True, pdf_url, None

        return False, None, "Unpaywall: PDF OA non trouvé dans les locations"
    except Exception as e:
        return False, None, f"Unpaywall erreur: {e}"


def fetch_pdf_from_unpaywall(doi, email):
    """Tente de récupérer un PDF via Unpaywall."""
    if not doi:
        return None, "Pas de DOI"

    try:
        url = f"https://api.unpaywall.org/v2/{doi}"
        params = {"email": email}
        r = requests.get(url, params=params, timeout=20)

        if r.status_code == 404:
            return None, "Unpaywall: DOI inconnu"
        if r.status_code != 200:
            return None, f"Unpaywall HTTP {r.status_code}"

        data = r.json()

        if not data.get("is_oa"):
            return None, "Unpaywall: pas Open Access"

        headers = {"User-Agent": "Mozilla/5.0"}

        best = data.get("best_oa_location")
        if best and best.get("url_for_pdf"):
            pdf_url = best["url_for_pdf"]
            r2 = requests.get(pdf_url, headers=headers, timeout=30)
            if r2.status_code == 200 and "application/pdf" in r2.headers.get("Content-Type", ""):
                return r2.content, None

        for loc in data.get("oa_locations", []):
            pdf_url = loc.get("url_for_pdf")
            if not pdf_url:
                continue
            try:
                r3 = requests.get(pdf_url, headers=headers, timeout=30)
                if r3.status_code == 200 and "application/pdf" in r3.headers.get("Content-Type", ""):
                    return r3.content, None
            except Exception:
                continue

        return None, "Unpaywall: PDF non trouvé"

    except Exception as e:
        return None, f"Unpaywall erreur: {e}"


def fetch_pdf_cascade(pmid, doi, pmcid, unpaywall_email, utiliser_scihub=False):
    """Cascade optimisée de récupération PDF avec multiples sources."""
    reasons = {}

    if doi:
        pdf, err = fetch_pdf_from_unpaywall(doi, unpaywall_email)
        if pdf:
            return pdf, "Unpaywall"
        reasons["Unpaywall"] = err
    else:
        reasons["Unpaywall"] = "Pas de DOI"

    msg = "Échec récupération PDF. Sources testées:\n"
    for source, reason in reasons.items():
        msg += f"  • {source}: {reason}\n"

    return None, msg.strip()


def extract_with_pypdf(pdf_content: bytes) -> str:
    """Extraction via pypdf."""
    try:
        reader = pypdf.PdfReader(BytesIO(pdf_content))
        pages = min(len(reader.pages), 20)
        out = []
        for i in range(pages):
            try:
                txt = reader.pages[i].extract_text()
                if txt:
                    out.append(txt)
            except Exception:
                pass
        return "\n\n".join(out)
    except Exception:
        return ""


def extract_text_from_pdf(pdf_content: bytes):
    """Extraction de texte PDF."""
    txt = extract_with_pypdf(pdf_content)
    if len(txt) > 100:
        return nettoyer_texte_pdf(txt), "pypdf"

    return "", "echec_extraction"


# ============================================
# PARTIE 6 — EXPORT NOTEBOOKLM
# ============================================

def build_pdf_from_text(titre: str, contenu: str) -> bytes:
    """Génère un PDF simple (A4) contenant le titre et le texte."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Paramètres de base
    x_margin = 50
    y_margin = 50
    max_width = width - 2 * x_margin
    line_height = 14

    # Fonction de découpe de ligne
    def wrap_text(text, canvas_obj, max_width):
        words = text.split()
        lines = []
        line = ""
        for w in words:
            test_line = (line + " " + w).strip()
            if canvas_obj.stringWidth(test_line, "Helvetica", 11) <= max_width:
                line = test_line
            else:
                lines.append(line)
                line = w
        if line:
            lines.append(line)
        return lines

    y = height - y_margin

    # Titre
    c.setFont("Helvetica-Bold", 14)
    for line in wrap_text(titre, c, max_width):
        c.drawString(x_margin, y, line)
        y -= line_height
    y -= 2 * line_height

    # Corps
    c.setFont("Helvetica", 11)
    for paragraphe in contenu.split("\n"):
        paragraphe = paragraphe.strip()
        if not paragraphe:
            y -= line_height
            continue
        for line in wrap_text(paragraphe, c, max_width):
            if y < y_margin:
                c.showPage()
                y = height - y_margin
                c.setFont("Helvetica", 11)
            c.drawString(x_margin, y, line)
            y -= line_height

    c.showPage()
    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

def build_notebooklm_export(meta, texte_fr: str) -> str:
    """Construit un fichier texte complet pour NotebookLM."""
    return f"""# VEILLE MEDICALE - {maintenant_str()}
Titre: {meta.get('title_fr')}
Titre original: {meta.get('title_en')}
Journal: {meta['journal']} ({meta['year']})
PMID: {meta['pmid']}
DOI: {meta.get('doi') or 'N/A'}

Texte complet traduit:
{texte_fr}
"""


def bouton_download_ios_safe(label: str, content: str, filename: str):
    """Génère un lien de téléchargement compatible iPhone."""
    b64 = base64.b64encode(content.encode()).decode()
    href = (
        f'<a href="data:text/plain;base64,{b64}" '
        f'download="{filename}" '
        f'style="text-decoration:none; font-weight:600;">{label}</a>'
    )
    return href

def bouton_download_pdf_ios_safe(label: str, pdf_bytes: bytes, filename: str):
    """Génère un lien de téléchargement PDF compatible iPhone."""
    b64 = base64.b64encode(pdf_bytes).decode()
    href = (
        f'<a href="data:application/pdf;base64,{b64}" '
        f'download="{filename}" '
        f'style="text-decoration:none; font-weight:600;">{label}</a>'
    )
    return href
    
@st.cache_data(ttl=60 * 60 * 24 * 5)  # 5 jours
def get_traductions_pdf_historiques(entries):
    """Persiste la liste des traductions PDF pendant quelques jours (si le cache n'est pas vidé)."""
    return entries

# ============================================
# PARTIE 7 — INTERFACE : SIDEBAR & PARAMÈTRES
# ============================================

with st.sidebar:
    st.header("⚙️ Paramètres de recherche")

    st.session_state.debug = st.checkbox("Activer le mode debug", value=st.session_state.debug)

    st.subheader("🔬 Mode de recherche")
    mode_recherche = st.radio(
        "Choisir le mode",
        ["Par mots-clés", "Par spécialité médicale"],
        index=0
    )

    mots_cles_fr = ""
    specialite = None
    choix_journaux = []
    inclure_keywords = False

    if mode_recherche == "Par mots-clés":
        mots_cles_fr = st.text_input(
            "Mots-clés",
            placeholder="diabète, hypertension..."
        )

        if mots_cles_fr.strip():
            try:
                with st.spinner("Traduction des mots-clés..."):
                    trad_preview = traduire_mots_cles_gemini(mots_cles_fr, G_KEY)
                    st.caption("Traduction EN pour PubMed :")
                    st.code(trad_preview)
            except Exception as e:
                st.warning(f"Erreur traduction mots-clés: {e}")

    else:
        specialite = st.selectbox("Spécialité médicale", list(SPECIALITES.keys()))
        journaux_dispo = SPECIALITES[specialite]["journaux"]

        choix_journaux = st.multiselect(
            "Journaux à inclure (laisser vide = tous)",
            journaux_dispo
        )
        
        # Si aucun journal sélectionné, utiliser tous les journaux
        if not choix_journaux:
            choix_journaux = journaux_dispo

        inclure_keywords = st.checkbox("Ajouter des mots-clés supplémentaires")
        if inclure_keywords:
            mots_cles_fr = st.text_input(
                "Mots-clés supplémentaires",
                placeholder="diabète, hypertension..."
            )
            if mots_cles_fr.strip():
                try:
                    with st.spinner("Traduction des mots-clés..."):
                        trad_preview = traduire_mots_cles_gemini(mots_cles_fr, G_KEY)
                        st.caption("Traduction EN pour PubMed :")
                        st.code(trad_preview)
                except Exception as e:
                    st.warning(f"Erreur traduction mots-clés: {e}")

    date_debut = st.date_input("Date début", value=date(2024, 1, 1))
    date_fin = st.date_input("Date fin", value=date.today())

    st.write(f"📆 Période sélectionnée : {date_debut.strftime('%d/%m/%Y')} → {date_fin.strftime('%d/%m/%Y')}")

    langue = st.selectbox("Langue", ["Toutes", "Anglais uniquement", "Français uniquement"])
    langue_code = "eng" if langue == "Anglais uniquement" else "fre" if langue == "Français uniquement" else ""

    type_etude_label = st.selectbox(
        "Type d'étude",
        ["Aucun filtre", "Essais cliniques", "Méta-analyses", "Revues systématiques"]
    )
    mapping_types = {
        "Aucun filtre": "",
        "Essais cliniques": "Clinical Trial",
        "Méta-analyses": "Meta-Analysis",
        "Revues systématiques": "Systematic Review"
    }
    type_etude = mapping_types[type_etude_label]

    nb_max = st.slider("Nombre max d'articles", 10, 200, 50, 10)
    
    type_acces = st.selectbox(
        "Type d'accès",
        ["Tous les articles", "Titre + abstract disponibles", "PDF gratuit uniquement"]
    )

    lancer = st.button("🔍 Lancer la recherche", type="primary", use_container_width=True)

    st.markdown("---")
    st.subheader("🕘 Historique des recherches")
    if st.session_state.historique:
        for h in st.session_state.historique[-10:]:
            st.markdown(f"- **{h.get('title_fr', 'Sans titre')}** ({h.get('journal', 'N/A')} {h.get('year', 'N/A')}) – PMID {h.get('pmid', 'N/A')}")

st.subheader("📂 Traductions PDF récentes")
if st.session_state.get("traductions_pdf"):
    for item in st.session_state.traductions_pdf[-10:]:
        st.markdown(
            f"- **{item['title_fr']} / {item['title_en']}** "
            f"({item['journal']} {item['year']}) – PMID {item['pmid']}"
        )


# ============================================
# PARTIE 8 — LOGIQUE DE RECHERCHE (CORRIGÉE)
# ============================================

if lancer:
    st.info("🔍 Recherche lancée...")

    st.session_state.articles = []
    st.session_state.details = {}

    # Vérification mots-clés si mode mots-clés
    if mode_recherche == "Par mots-clés" and not mots_cles_fr.strip():
        st.error("❌ Merci de saisir au moins un mot-clé.")
        st.stop()

    try:
        # -----------------------------
        # 1) Construction de la requête
        # -----------------------------
        if mode_recherche == "Par mots-clés":
            st.info("📝 Traduction des mots-clés...")
            mots_cles_en = traduire_mots_cles_gemini(mots_cles_fr, G_KEY)
            base_query = mots_cles_en

            if st.session_state.debug:
                st.write(f"🔍 Requête base (mots-clés) : {base_query}")

        else:
            base_query = SPECIALITES[specialite]["mesh_terms"]

            # Ajout éventuel de mots-clés supplémentaires
            if inclure_keywords and mots_cles_fr.strip():
                mots_cles_en = traduire_mots_cles_gemini(mots_cles_fr, G_KEY)
                base_query += f" AND ({mots_cles_en})"

            if choix_journaux:
                journaux_query = " OR ".join([f'"{j}"[Journal]' for j in choix_journaux])
                base_query += f" AND ({journaux_query})"

            if st.session_state.debug:
                st.write(f"🔍 Requête base (spécialité) : {base_query}")

        # Construction finale
        query = construire_query_pubmed(
            base_query,
            date_debut,
            date_fin,
            langue_code,
            type_etude
        )

        if st.session_state.debug:
            st.code(query, language="text")

        # -----------------------------
        # 2) Recherche des PMIDs
        # -----------------------------
        pmids = pubmed_search_ids(query, max_results=nb_max)

        if not pmids:
            st.warning("Aucun article trouvé pour cette requête.")
            st.stop()

        st.success(f"📄 {len(pmids)} articles trouvés")

        # -----------------------------
        # 3) Récupération métadonnées
        # -----------------------------
        articles = pubmed_fetch_metadata_and_abstracts(pmids)

        if not articles:
            st.error("❌ Impossible de récupérer les métadonnées PubMed.")
            st.stop()

        st.session_state.articles = articles

        # -----------------------------
        # 4) Filtrage selon type d'accès
        # -----------------------------
        articles_affiches = []

        for meta in articles:
            has_abstract = bool(meta.get("abstract_en"))
            has_doi = bool(meta.get("doi"))

            if type_acces == "Titre + abstract disponibles" and not has_abstract:
                continue

            if type_acces == "PDF gratuit uniquement":
                ok, url_pdf, reason = check_pdf_free_unpaywall(meta.get("doi"), UNPAYWALL_EMAIL)
                if not ok:
                    if st.session_state.debug:
                        st.warning(f"PMID {meta['pmid']} — PDF non disponible : {reason}")
                    continue

            articles_affiches.append(meta)

        # -----------------------------
       # -----------------------------
# 5) Affichage des résultats
# -----------------------------
st.subheader("📑 Résultats de la recherche")

if not articles_affiches:
    st.warning("Aucun article ne correspond aux critères d'accès sélectionnés.")
else:
    for meta in articles_affiches:
        with st.expander(f"{meta['title_en']} ({meta['journal']} {meta['year']})"):

            # Métadonnées
            st.write(f"**PMID :** {meta['pmid']}")
            st.write(f"**DOI :** {meta.get('doi', 'N/A')}")

            # Abstract EN
            st.write("### Abstract (EN)")
            st.write(meta.get("abstract_en", "Non disponible"))

            # Traduction du titre
            with st.expander("🇫🇷 Traduction du titre"):
                st.write(traduire_avec_fallback(meta["title_en"]))

            # Traduction de l'abstract
            with st.expander("🇫🇷 Traduction de l'abstract"):
                st.write(traduire_avec_fallback(meta["abstract_en"]))

            # Résumé court
            with st.expander("📝 Résumé court"):
                st.write(resumer_avec_fallback(meta["abstract_en"], mode="court"))

            # Résumé long
            with st.expander("📘 Résumé long"):
                st.write(resumer_avec_fallback(meta["abstract_en"], mode="long"))

except Exception as e:
    st.error(f"❌ Erreur lors de la recherche : {e}")

# ============================================
# PARTIE 9 — AFFICHAGE DES ARTICLES
# ============================================

total_articles = len(st.session_state.articles)

if total_articles > 0:
    st.success(f"📊 {total_articles} articles disponibles")
    
    for art in st.session_state.articles:
        pmid = art["pmid"]

        with st.expander(f"{art['title_fr']} ({art['journal']} {art['year']}) - PMID {pmid}"):

            st.markdown(f"**Titre original (EN) :** *{art['title_en']}*")
            st.write(f"**Journal :** {art['journal']} ({art['year']})")
            st.write(f"**PMID :** {pmid}")
            st.write(f"**DOI :** {art.get('doi') or 'N/A'}")
            st.write(f"**PMCID :** {art.get('pmcid') or 'N/A'}")

            if art["abstract_fr"]:
                st.markdown("### 🧾 Abstract (FR)")
                st.write(art["abstract_fr"])

            if art["abstract_en"]:
                with st.expander("Voir abstract original (EN)"):
                    st.write(art["abstract_en"])

            # Indication de disponibilité PDF OA
            if art.get("has_free_pdf"):
                st.success("✅ PDF gratuit (Open Access) disponible")
            else:
                st.info("ℹ️ PDF gratuit non identifié via Unpaywall")

            # Sélection et extraction/traduction du PDF pour cet article
            if art.get("has_free_pdf"):
                if st.button(
                    "📄 Extraire & traduire le PDF en français",
                    key=f"btn_extract_{pmid}"
                ):
                    with st.spinner("Récupération du PDF et traduction..."):
                        # Récupération du PDF via cascade
                        pdf_content, source_msg = fetch_pdf_cascade(
                            pmid=art["pmid"],
                            doi=art.get("doi"),
                            pmcid=art.get("pmcid"),
                            unpaywall_email=UNPAYWALL_EMAIL,
                            utiliser_scihub=False
                        )

                        if not pdf_content:
                            st.error(f"Impossible de récupérer le PDF : {source_msg}")
                        else:
                            texte_pdf_en, methode = extract_text_from_pdf(pdf_content)
                            texte_pdf_en = tronquer(texte_pdf_en, max_len=12000)

                            if not texte_pdf_en:
                                st.warning("Texte PDF non exploitable ou trop court.")
                            else:
                                texte_pdf_fr = traduire_long_texte_cache(
                                    texte_pdf_en,
                                    MODE_TRAD,
                                    deepl_key=DEEPL_KEY,
                                    g_key=G_KEY,
                                    chunk_size=2000
                                )

                                # Construire un texte structuré pour NotebookLM
                                contenu_notebooklm = build_notebooklm_export(
                                    art,
                                    texte_pdf_fr
                                )

                                # Générer le PDF
                                titre_pdf = f"{art.get('title_fr') or art.get('title_en')}"
                                pdf_bytes = build_pdf_from_text(
                                    titre_pdf,
                                    contenu_notebooklm
                                )
                                filename = f"veille_{art['pmid']}.pdf"

                                # Bouton de téléchargement classique
                                st.download_button(
                                    label="⬇️ Télécharger la traduction en PDF",
                                    data=pdf_bytes,
                                    file_name=filename,
                                    mime="application/pdf",
                                    key=f"download_{pmid}"
                                )

                                # Lien iOS-safe
                                st.markdown(
                                    bouton_download_pdf_ios_safe(
                                        "⬇️ Télécharger pour iPhone / iPad",
                                        pdf_bytes,
                                        filename
                                    ),
                                    unsafe_allow_html=True
                                )

                                # Sauvegarde dans un historique de traductions
                                if "traductions_pdf" not in st.session_state:
                                    st.session_state.traductions_pdf = []
                                st.session_state.traductions_pdf.append({
                                    "timestamp": maintenant_str(),
                                    "pmid": art["pmid"],
                                    "title_fr": art.get("title_fr"),
                                    "title_en": art.get("title_en"),
                                    "journal": art.get("journal"),
                                    "year": art.get("year"),
                                    "filename": filename
                                })
                                get_traductions_pdf_historiques(st.session_state.traductions_pdf)

                                st.success("✅ PDF extrait, traduit et prêt pour NotebookLM.")
else:
    st.info("👈 Utilisez le menu latéral pour lancer une recherche")
