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

DEEPL_KEY = st.secrets.get("DEEPL_KEY", None)
if DEEPL_KEY:
    st.sidebar.success("✅ Clé DeepL chargée")
else:
    st.sidebar.info("ℹ️ DeepL non configuré, utilisation de Gemini")

UNPAYWALL_EMAIL = st.secrets.get("UNPAYWALL_EMAIL", "example@email.com")

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
# PARTIE 3 — TRADUCTION (DEEPL / GEMINI)
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
                t = traduire_gemini_chunk(chunk, g_key)
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
        return traduire_gemini_chunk(texte, g_key)


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

    lancer = st.button("🔍 Lancer la recherche", type="primary", use_container_width=True)

    st.markdown("---")
    st.subheader("🕘 Historique des recherches")
    if st.session_state.historique:
        for h in st.session_state.historique[-10:]:
            st.markdown(f"- **{h.get('title_fr', 'Sans titre')}** ({h.get('journal', 'N/A')} {h.get('year', 'N/A')}) – PMID {h.get('pmid', 'N/A')}")


# ============================================
# PARTIE 8 — LOGIQUE DE RECHERCHE
# ============================================

if lancer:
    st.info("🔍 Recherche lancée...")
    
    st.session_state.articles = []
    st.session_state.details = {}

    if mode_recherche == "Par mots-clés" and not mots_cles_fr.strip():
        st.error("❌ Merci de saisir au moins un mot-clé.")
    else:
        try:
            # Construction de la requête
            if mode_recherche == "Par mots-clés":
                st.info("📝 Traduction des mots-clés...")
                mots_cles_en = traduire_mots_cles_gemini(mots_cles_fr, G_KEY)
                base_query = mots_cles_en
                if st.session_state.debug:
                    st.write(f"🔍 Requête base (mots-clés): {base_query}")

            else:
                base_query = SPECIALITES[specialite]["mesh_terms"]
                if st.session_state.debug:
                    st.write(f"🔍 Requête base (spécialité): {base_query}")

                if choix_journaux:
                    journaux_query = " OR ".join([f'"{j}"[Journal]' for j in choix_journaux])
                    base_query += f" AND ({journaux_query})"
                    if st.session_state.debug:
                        st.write(f"📚 Journaux ajoutés: {journaux_query}")

                if inclure_keywords and mots_cles_fr.strip():
                    st.info("📝 Traduction des mots-clés supplémentaires...")
                    mots_cles_en_sup = traduire_mots_cles_gemini(mots_cles_fr, G_KEY)
                    base_query += f" AND ({mots_cles_en_sup})"
                    if st.session_state.debug:
                        st.write(f"🔍 Mots-clés supplémentaires: {mots_cles_en_sup}")

            # Construction requête complète
            query = construire_query_pubmed(
                base_query,
                date_debut,
                date_fin,
                langue_code=langue_code,
                type_etude=type_etude
            )

            if st.session_state.debug:
                st.info(f"🔍 Requête PubMed finale:\n```\n{query}\n```")

            # Recherche PMIDs
            st.info("🔍 Recherche des articles sur PubMed...")
            pmids = pubmed_search_ids(query, max_results=nb_max)
            
            if not pmids:
                st.warning("⚠️ Aucun article trouvé avec ces critères.")
                st.stop()
            
            st.success(f"✅ {len(pmids)} articles trouvés")

            # Récupération métadonnées
            st.info("📥 Récupération des métadonnées...")
            meta_list = pubmed_fetch_metadata_and_abstracts(pmids)
            
            if not meta_list:
                st.warning("⚠️ Impossible de récupérer les métadonnées.")
                st.stop()
            
            st.success(f"✅ {len(meta_list)} métadonnées récupérées")

            # Traduction titres + abstracts
            st.info("🌐 Traduction des titres et résumés...")
            articles = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, art in enumerate(meta_list):
                try:
                    status_text.text(f"Traduction de l'article {idx + 1}/{len(meta_list)}...")
                    
                    art["title_fr"] = traduire_texte_court_cache(
                        art["title_en"], MODE_TRAD, DEEPL_KEY, G_KEY
                    )

                    art["abstract_fr"] = (
                        traduire_long_texte_cache(
                            art["abstract_en"], MODE_TRAD, DEEPL_KEY, G_KEY, chunk_size=2000
                        )
                        if art["abstract_en"] else ""
                    )

                    articles.append(art)

                    st.session_state.historique.append({
                        "pmid": art["pmid"],
                        "title_en": art["title_en"],
                        "title_fr": art["title_fr"],
                        "journal": art["journal"],
                        "year": art["year"],
                        "doi": art.get("doi"),
                        "pmcid": art.get("pmcid")
                    })
                    
                    progress_bar.progress((idx + 1) / len(meta_list))
                    
                    # Petit délai pour éviter le rate limiting
                    import time
                    time.sleep(0.5)
                    
                except Exception as e:
                    st.warning(f"⚠️ Erreur traduction article {art.get('pmid')}: {e}")
                    # Ajouter l'article même si la traduction échoue
                    art["title_fr"] = art["title_en"]
                    art["abstract_fr"] = art["abstract_en"]
                    articles.append(art)

            status_text.empty()
            st.session_state.articles = articles
            st.success(f"✅ {len(articles)} articles traduits avec succès!")

        except Exception as e:
            st.error(f"❌ Erreur globale : {e}")
            if st.session_state.debug:
                import traceback
                st.code(traceback.format_exc())


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
else:
    st.info("👈 Utilisez le menu latéral pour lancer une recherche")
