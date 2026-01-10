import streamlit as st
import requests
import xml.etree.ElementTree as ET
from datetime import date, datetime
from io import BytesIO
import tarfile
import re
import pypdf
import google.generativeai as genai

###########################
# CONFIG GÉNÉRALE & DEBUG #
###########################

st.set_page_config(page_title="Veille Médicale Pro", layout="wide")
st.title("🩺 Veilimport streamlit as st
import requests
import xml.etree.ElementTree as ET
from datetime import date, datetime
from io import BytesIO
import tarfile
import re
import pypdf
import google.generativeai as genai

###########################
# CONFIG GÉNÉRALE & DEBUG #
###########################

st.set_page_config(page_title="Veille Médicale Pro", layout="wide")
st.title("🩺 Veille Médicale Professionnelle")

# Récupération des clés
try:
    G_KEY = st.secrets["GEMINI_KEY"]
except Exception:
    st.error("⚠️ Clé GEMINI_KEY manquante dans st.secrets")
    st.stop()

DEEPL_KEY = st.secrets.get("DEEPL_KEY", None)
UNPAYWALL_EMAIL = st.secrets.get("UNPAYWALL_EMAIL", "example@email.com")

MODE_TRAD = "deepl" if DEEPL_KEY else "gemini"

if "articles" not in st.session_state:
    st.session_state.articles = []
if "details" not in st.session_state:
    st.session_state.details = {}
if "debug" not in st.session_state:
    st.session_state.debug = False

###########################
# UTILITAIRES GÉNÉRIQUES  #
###########################

def maintenant_str() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")

def nettoyer_titre(titre: str) -> str:
    """Nettoie le titre d'article : balises HTML, mentions 'see more', espaces."""
    if not titre:
        return "Titre non disponible"

    titre = re.sub(r'<[^>]+>', '', titre)

    patterns = [
        r'\s*see\s+more\s*',
        r'\s*\[see\s+more\]\s*',
        r'\s*\(see\s+more\)\s*',
        r'\s*`\(see\s+more\)`\s*',
        r'\s*voir\s+plus\s*',
        r'\s*\[voir\s+plus\]\s*',
        r'\s*\(voir\s+plus\)\s*',
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
    if not texte:
        return texte
    if len(texte) <= max_len:
        return texte
    return texte[:max_len] + "\n\n[Texte tronqué pour analyse]"

###########################
# TRADUCTION (DEEPL/GEMINI)
###########################

def traduire_deepl_chunk(texte: str, api_key: str) -> str:
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
    genai.configure(api_key=g_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
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
    trad = resp.text.strip()
    trad = trad.replace("**", "")
    trad = re.sub(r'^(Traduction\s*:?\s*)', '', trad, flags=re.IGNORECASE)
    trad = nettoyer_titre(trad)
    return trad

@st.cache_data(show_spinner=False)
def traduire_long_texte_cache(texte: str,
                              mode: str,
                              deepl_key: str = None,
                              g_key: str = None,
                              chunk_size: int = 4000) -> str:
    texte = texte.strip()
    if not texte:
        return texte
    chunks = [texte[i:i+chunk_size] for i in range(0, len(texte), chunk_size)]
    trad_total = []
    for chunk in chunks:
        if mode == "deepl" and deepl_key:
            t = traduire_deepl_chunk(chunk, deepl_key)
        else:
            t = traduire_gemini_chunk(chunk, g_key)
        trad_total.append(t)
    return "\n\n".join(trad_total)

@st.cache_data(show_spinner=False)
def traduire_texte_court_cache(texte: str,
                               mode: str,
                               deepl_key: str = None,
                               g_key: str = None) -> str:
    texte = texte.strip()
    if not texte:
        return texte
    if mode == "deepl" and deepl_key:
        return traduire_deepl_chunk(texte, deepl_key)
    else:
        return traduire_gemini_chunk(texte, g_key)

@st.cache_data(show_spinner=False)
def traduire_mots_cles_gemini(mots_cles_fr: str, g_key: str) -> str:
    genai.configure(api_key=g_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
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

###########################
# PUBMED : RECHERCHE      #
###########################

BASE_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

def construire_query_pubmed(mots_cles_en: str,
                            date_debut,
                            date_fin,
                            langue_code: str = "",
                            type_etude: str = "") -> str:
    query = mots_cles_en.strip()
    if date_debut and date_fin:
        query += f' AND ("{date_debut:%Y/%m/%d}"[Date - Publication] : "{date_fin:%Y/%m/%d}"[Date - Publication])'
    if langue_code:
        query += f' AND {langue_code}[lang]'
    if type_etude:
        query += f' AND {type_etude}[pt]'
    return query

@st.cache_data(show_spinner=False)
def pubmed_search_ids(query: str, max_results: int = 50):
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

@st.cache_data(show_spinner=False)
def pubmed_fetch_metadata_and_abstracts(pmids):
    if not pmids:
        return []
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
###########################
# RÉCUPÉRATION PDF        #
###########################

def fetch_pdf_from_unpaywall(doi, email):
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


@st.cache_data(show_spinner=False)
###########################
# FONCTIONS PDF MANQUANTES #
###########################

def _clean_pmcid(pmcid: str) -> str:
    """Nettoie le PMCID en enlevant le préfixe PMC s'il existe."""
    if not pmcid:
        return ""
    return pmcid.replace("PMC", "").strip()


def fetch_pdf_from_pmc_ftp(pmcid):
    """Tente de récupérer le PDF depuis le serveur FTP de PMC."""
    if not pmcid:
        return None, "Pas de PMCID"
    
    try:
        clean_id = _clean_pmcid(pmcid)
        # Construction de l'URL FTP
        # Format: ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/XX/YY/PMCxxxxxxx.tar.gz
        # où XX/YY sont les 2 premiers groupes de chiffres du PMCID
        
        if len(clean_id) < 2:
            return None, "PMCID invalide"
        
        subdir1 = clean_id[:2]
        subdir2 = clean_id[2:4] if len(clean_id) >= 4 else "00"
        
        ftp_url = f"ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/{subdir1}/{subdir2}/PMC{clean_id}.tar.gz"
        
        # Téléchargement du fichier tar.gz
        r = requests.get(ftp_url, timeout=30)
        if r.status_code != 200:
            return None, f"PMC FTP: HTTP {r.status_code}"
        
        # Extraction du PDF depuis l'archive tar.gz
        tar_buffer = BytesIO(r.content)
        with tarfile.open(fileobj=tar_buffer, mode='r:gz') as tar:
            for member in tar.getmembers():
                if member.name.endswith('.pdf'):
                    pdf_file = tar.extractfile(member)
                    if pdf_file:
                        return pdf_file.read(), None
        
        return None, "PMC FTP: PDF non trouvé dans l'archive"
    
    except Exception as e:
        return None, f"PMC FTP erreur: {e}"


def fetch_pdf_from_pmc_web(pmcid):
    """Tente de récupérer le PDF depuis le site web de PMC."""
    if not pmcid:
        return None, "Pas de PMCID"
    
    try:
        clean_id = _clean_pmcid(pmcid)
        pmc_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{clean_id}/pdf/"
        
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(pmc_url, headers=headers, timeout=30, allow_redirects=True)
        
        if r.status_code != 200:
            return None, f"PMC Web: HTTP {r.status_code}"
        
        if "application/pdf" in r.headers.get("Content-Type", ""):
            return r.content, None
        
        return None, "PMC Web: pas un PDF"
    
    except Exception as e:
        return None, f"PMC Web erreur: {e}"


def fetch_pdf_from_europe_pmc(pmid, pmcid=None):
    """Tente de récupérer le PDF depuis Europe PMC."""
    if not pmid and not pmcid:
        return None, "Pas de PMID ni PMCID"
    
    try:
        # Europe PMC accepte soit PMID soit PMCID
        identifier = f"PMC{_clean_pmcid(pmcid)}" if pmcid else pmid
        eu_url = f"https://europepmc.org/api/fulltextRepo?pmid={identifier}"
        
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(eu_url, headers=headers, timeout=30)
        
        if r.status_code != 200:
            return None, f"EuropePMC: HTTP {r.status_code}"
        
        # Analyse de la réponse XML pour trouver le lien PDF
        try:
            root = ET.fromstring(r.content)
            pdf_link = root.find('.//link[@format="pdf"]')
            
            if pdf_link is not None and pdf_link.get('href'):
                pdf_url = pdf_link.get('href')
                r2 = requests.get(pdf_url, headers=headers, timeout=30)
                
                if r2.status_code == 200 and "application/pdf" in r2.headers.get("Content-Type", ""):
                    return r2.content, None
        except ET.ParseError:
            pass
        
        return None, "EuropePMC: PDF non trouvé"
    
    except Exception as e:
        return None, f"EuropePMC erreur: {e}"
        
def fetch_pdf_cascade(pmid, doi, pmcid, unpaywall_email, utiliser_scihub=False):
    """Cascade optimisée de récupération PDF."""
    # 1. PMC FTP
    if pmcid:
        pdf, err = fetch_pdf_from_pmc_ftp(pmcid)
        if pdf:
            return pdf, f"PMC FTP (PMC{_clean_pmcid(pmcid)})"
        reason_ftp = err
    else:
        reason_ftp = "Pas de PMCID"

    # 2. PMC Web
    if pmcid:
        pdf, err = fetch_pdf_from_pmc_web(pmcid)
        if pdf:
            return pdf, f"PMC Web (PMC{_clean_pmcid(pmcid)})"
        reason_web = err
    else:
        reason_web = "Pas de PMCID"

    # 3. EuropePMC
    pdf, err = fetch_pdf_from_europe_pmc(pmid, pmcid)
    if pdf:
        return pdf, "EuropePMC"
    reason_eu = err

    # 4. Unpaywall
    if doi:
        pdf, err = fetch_pdf_from_unpaywall(doi, unpaywall_email)
        if pdf:
            return pdf, "Unpaywall"
        reason_up = err
    else:
        reason_up = "Pas de DOI"

    # 5. Sci-Hub (désactivé)
    reason_sh = "Sci-Hub désactivé"

    msg = (
        f"Échec cascade PDF. "
        f"PMC FTP: {reason_ftp} | "
        f"PMC Web: {reason_web} | "
        f"EuropePMC: {reason_eu} | "
        f"Unpaywall: {reason_up} | "
        f"Sci-Hub: {reason_sh}"
    )
    return None, msg


###########################
# EXTRACTION TEXTE PDF    #
###########################

def extract_with_pymupdf(pdf_content: bytes) -> str:
    try:
        import fitz
    except ImportError:
        return ""
    try:
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        pages = min(len(doc), 20)
        return "\n\n".join(doc.load_page(i).get_text("text") for i in range(pages))
    except Exception:
        return ""


def extract_with_pdfplumber(pdf_content: bytes) -> str:
    try:
        import pdfplumber
    except ImportError:
        return ""
    try:
        with pdfplumber.open(BytesIO(pdf_content)) as pdf:
            pages = min(len(pdf.pages), 20)
            return "\n\n".join(
                pdf.pages[i].extract_text() or "" for i in range(pages)
            )
    except Exception:
        return ""


def extract_with_pypdf(pdf_content: bytes) -> str:
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
    """Essaie plusieurs moteurs successivement."""
    txt = extract_with_pymupdf(pdf_content)
    if len(txt) > 200:
        return txt, "pymupdf"

    txt = extract_with_pdfplumber(pdf_content)
    if len(txt) > 200:
        return txt, "pdfplumber"

    txt = extract_with_pypdf(pdf_content)
    if len(txt) > 200:
        return txt, "pypdf"

    return txt, "extraction_partielle"


###########################
# NOTEBOOKLM EXPORT       #
###########################

def build_notebooklm_export(meta, texte_fr: str) -> str:
    return f"""# VEILLE MEDICALE - {maintenant_str()}
Titre: {meta.get('title_fr')}
Titre original: {meta.get('title_en')}
Journal: {meta['journal']} ({meta['year']})
PMID: {meta['pmid']}
DOI: {meta.get('doi') or 'N/A'}

Texte complet traduit:
{texte_fr}
"""
###########################
# INTERFACE STREAMLIT     #
###########################

with st.sidebar:
    st.header("⚙️ Paramètres de recherche")

    st.session_state.debug = st.checkbox("Activer le mode debug", value=st.session_state.debug)

    mots_cles_fr = st.text_area("Mots-clés (FR)", "hypertension gravidique", height=80)

    if mots_cles_fr.strip():
        try:
            trad_preview = traduire_mots_cles_gemini(mots_cles_fr, G_KEY)
            st.caption("Traduction EN pour PubMed :")
            st.code(trad_preview)
        except Exception as e:
            st.warning(f"Erreur traduction mots-clés: {e}")

    date_debut = st.date_input("Date début", value=date(2024, 1, 1))
    date_fin = st.date_input("Date fin", value=date.today())

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

    utiliser_scihub = st.checkbox("Activer Sci-Hub (non implémenté)", value=False)

    lancer = st.button("🔍 Lancer la recherche", type="primary", use_container_width=True)


###########################
# LOGIQUE DE RECHERCHE    #
###########################

if lancer:
    st.session_state.articles = []
    st.session_state.details = {}

    if not mots_cles_fr.strip():
        st.error("Merci de saisir au moins un mot-clé.")
    else:
        with st.spinner("Recherche PubMed..."):
            try:
                mots_cles_en = traduire_mots_cles_gemini(mots_cles_fr, G_KEY)
                query = construire_query_pubmed(
                    mots_cles_en, date_debut, date_fin,
                    langue_code=langue_code, type_etude=type_etude
                )

                pmids = pubmed_search_ids(query, max_results=nb_max)
                meta_list = pubmed_fetch_metadata_and_abstracts(pmids)

                articles = []
                for art in meta_list:
                    # Traduction titre
                    art["title_fr"] = traduire_texte_court_cache(
                        art["title_en"], MODE_TRAD, DEEPL_KEY, G_KEY
                    )

                    # Traduction abstract
                    art["abstract_fr"] = traduire_long_texte_cache(
                        art["abstract_en"], MODE_TRAD, DEEPL_KEY, G_KEY, chunk_size=2000
                    ) if art["abstract_en"] else ""

                    articles.append(art)

                st.session_state.articles = articles

            except Exception as e:
                st.error(f"Erreur PubMed : {e}")


###########################
# AFFICHAGE DES ARTICLES  #
###########################

st.write(f"Résultats : {len(st.session_state.articles)} articles trouvés")

for art in st.session_state.articles:
    pmid = art["pmid"]

    if pmid not in st.session_state.details:
        st.session_state.details[pmid] = {
            "texte_en": None,
            "texte_fr": None,
            "source_pdf": None,
            "methode_extraction": None,
            "erreur": None,
        }

    det = st.session_state.details[pmid]

    with st.expander(f"{art['title_fr']} ({art['journal']} {art['year']}) - PMID {pmid}"):

        st.markdown(f"**Titre original (EN) :** *{art['title_en']}*")
        st.write(f"**Journal :** {art['journal']} ({art['year']})")
        st.write(f"**PMID :** {pmid}")
        st.write(f"**DOI :** {art.get('doi') or 'N/A'}")
        st.write(f"**PMCID :** {art.get('pmcid') or 'N/A'}")

        # Abstract FR
        if art["abstract_fr"]:
            st.markdown("### 🧾 Abstract (FR)")
            st.text(art["abstract_fr"])

        # Abstract EN
        if art["abstract_en"]:
            with st.expander("Voir abstract original (EN)"):
                st.text(art["abstract_en"])

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            if st.button(f"📥 Récupérer PDF + traduire (PMID {pmid})", key=f"btn_{pmid}"):

                with st.spinner("Téléchargement et extraction du PDF..."):
                    pdf_bytes, source = fetch_pdf_cascade(
                        pmid, art.get("doi"), art.get("pmcid"),
                        UNPAYWALL_EMAIL, utiliser_scihub
                    )

                    if not pdf_bytes:
                        det["erreur"] = source
                        st.error(f"Échec PDF : {source}")
                    else:
                        det["source_pdf"] = source
                        texte_en, methode = extract_text_from_pdf(pdf_bytes)
                        texte_en = nettoyer_texte_pdf(texte_en)

                        if len(texte_en) < 200:
                            det["erreur"] = "Texte extrait insuffisant"
                            st.error(det["erreur"])
                        else:
                            det["methode_extraction"] = methode
                            texte_en_tronque = tronquer(texte_en)
                            det["texte_en"] = texte_en_tronque

                            st.info("Traduction du PDF en cours...")
                            det["texte_fr"] = traduire_long_texte_cache(
                                texte_en_tronque, MODE_TRAD, DEEPL_KEY, G_KEY
                            )
                            st.success("PDF extrait et traduit avec succès")

        with col2:
            if det["texte_fr"]:
                st.write(f"**Source PDF :** {det['source_pdf']}")
                st.write(f"**Méthode extraction :** {det['methode_extraction']}")
                st.text(det["texte_fr"][:800])

                export_txt = build_notebooklm_export(art, det["texte_fr"])
                st.download_button(
                    "📥 Export NotebookLM",
                    data=export_txt,
                    file_name=f"notebooklm_pmid_{pmid}.txt",
                    mime="text/plain"
                )

            elif det["erreur"]:
                st.error(det["erreur"])le Médicale Professionnelle")

# Récupération des clés
try:
    G_KEY = st.secrets["GEMINI_KEY"]
except Exception:
    st.error("⚠️ Clé GEMINI_KEY manquante dans st.secrets")
    st.stop()

DEEPL_KEY = st.secrets.get("DEEPL_KEY", None)
UNPAYWALL_EMAIL = st.secrets.get("UNPAYWALL_EMAIL", "example@email.com")

MODE_TRAD = "deepl" if DEEPL_KEY else "gemini"

if "articles" not in st.session_state:
    st.session_state.articles = []
if "details" not in st.session_state:
    st.session_state.details = {}
if "debug" not in st.session_state:
    st.session_state.debug = False

###########################
# UTILITAIRES GÉNÉRIQUES  #
###########################

def maintenant_str() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")

def nettoyer_titre(titre: str) -> str:
    """Nettoie le titre d'article : balises HTML, mentions 'see more', espaces."""
    if not titre:
        return "Titre non disponible"

    titre = re.sub(r'<[^>]+>', '', titre)

    patterns = [
        r'\s*see\s+more\s*',
        r'\s*\[see\s+more\]\s*',
        r'\s*\(see\s+more\)\s*',
        r'\s*`\(see\s+more\)`\s*',
        r'\s*voir\s+plus\s*',
        r'\s*\[voir\s+plus\]\s*',
        r'\s*\(voir\s+plus\)\s*',
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
    if not texte:
        return texte
    if len(texte) <= max_len:
        return texte
    return texte[:max_len] + "\n\n[Texte tronqué pour analyse]"

###########################
# TRADUCTION (DEEPL/GEMINI)
###########################

def traduire_deepl_chunk(texte: str, api_key: str) -> str:
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
    genai.configure(api_key=g_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
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
    trad = resp.text.strip()
    trad = trad.replace("**", "")
    trad = re.sub(r'^(Traduction\s*:?\s*)', '', trad, flags=re.IGNORECASE)
    trad = nettoyer_titre(trad)
    return trad

@st.cache_data(show_spinner=False)
def traduire_long_texte_cache(texte: str,
                              mode: str,
                              deepl_key: str = None,
                              g_key: str = None,
                              chunk_size: int = 4000) -> str:
    texte = texte.strip()
    if not texte:
        return texte
    chunks = [texte[i:i+chunk_size] for i in range(0, len(texte), chunk_size)]
    trad_total = []
    for chunk in chunks:
        if mode == "deepl" and deepl_key:
            t = traduire_deepl_chunk(chunk, deepl_key)
        else:
            t = traduire_gemini_chunk(chunk, g_key)
        trad_total.append(t)
    return "\n\n".join(trad_total)

@st.cache_data(show_spinner=False)
def traduire_texte_court_cache(texte: str,
                               mode: str,
                               deepl_key: str = None,
                               g_key: str = None) -> str:
    texte = texte.strip()
    if not texte:
        return texte
    if mode == "deepl" and deepl_key:
        return traduire_deepl_chunk(texte, deepl_key)
    else:
        return traduire_gemini_chunk(texte, g_key)

@st.cache_data(show_spinner=False)
def traduire_mots_cles_gemini(mots_cles_fr: str, g_key: str) -> str:
    genai.configure(api_key=g_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
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

###########################
# PUBMED : RECHERCHE      #
###########################

BASE_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

def construire_query_pubmed(mots_cles_en: str,
                            date_debut,
                            date_fin,
                            langue_code: str = "",
                            type_etude: str = "") -> str:
    query = mots_cles_en.strip()
    if date_debut and date_fin:
        query += f' AND ("{date_debut:%Y/%m/%d}"[Date - Publication] : "{date_fin:%Y/%m/%d}"[Date - Publication])'
    if langue_code:
        query += f' AND {langue_code}[lang]'
    if type_etude:
        query += f' AND {type_etude}[pt]'
    return query

@st.cache_data(show_spinner=False)
def pubmed_search_ids(query: str, max_results: int = 50):
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

@st.cache_data(show_spinner=False)
def pubmed_fetch_metadata_and_abstracts(pmids):
    if not pmids:
        return []
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
###########################
# RÉCUPÉRATION PDF        #
###########################

def fetch_pdf_from_unpaywall(doi, email):
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


@st.cache_data(show_spinner=False)
###########################
# FONCTIONS PDF MANQUANTES #
###########################

def _clean_pmcid(pmcid: str) -> str:
    """Nettoie le PMCID en enlevant le préfixe PMC s'il existe."""
    if not pmcid:
        return ""
    return pmcid.replace("PMC", "").strip()


def fetch_pdf_from_pmc_ftp(pmcid):
    """Tente de récupérer le PDF depuis le serveur FTP de PMC."""
    if not pmcid:
        return None, "Pas de PMCID"
    
    try:
        clean_id = _clean_pmcid(pmcid)
        # Construction de l'URL FTP
        # Format: ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/XX/YY/PMCxxxxxxx.tar.gz
        # où XX/YY sont les 2 premiers groupes de chiffres du PMCID
        
        if len(clean_id) < 2:
            return None, "PMCID invalide"
        
        subdir1 = clean_id[:2]
        subdir2 = clean_id[2:4] if len(clean_id) >= 4 else "00"
        
        ftp_url = f"ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/{subdir1}/{subdir2}/PMC{clean_id}.tar.gz"
        
        # Téléchargement du fichier tar.gz
        r = requests.get(ftp_url, timeout=30)
        if r.status_code != 200:
            return None, f"PMC FTP: HTTP {r.status_code}"
        
        # Extraction du PDF depuis l'archive tar.gz
        tar_buffer = BytesIO(r.content)
        with tarfile.open(fileobj=tar_buffer, mode='r:gz') as tar:
            for member in tar.getmembers():
                if member.name.endswith('.pdf'):
                    pdf_file = tar.extractfile(member)
                    if pdf_file:
                        return pdf_file.read(), None
        
        return None, "PMC FTP: PDF non trouvé dans l'archive"
    
    except Exception as e:
        return None, f"PMC FTP erreur: {e}"


def fetch_pdf_from_pmc_web(pmcid):
    """Tente de récupérer le PDF depuis le site web de PMC."""
    if not pmcid:
        return None, "Pas de PMCID"
    
    try:
        clean_id = _clean_pmcid(pmcid)
        pmc_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{clean_id}/pdf/"
        
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(pmc_url, headers=headers, timeout=30, allow_redirects=True)
        
        if r.status_code != 200:
            return None, f"PMC Web: HTTP {r.status_code}"
        
        if "application/pdf" in r.headers.get("Content-Type", ""):
            return r.content, None
        
        return None, "PMC Web: pas un PDF"
    
    except Exception as e:
        return None, f"PMC Web erreur: {e}"


def fetch_pdf_from_europe_pmc(pmid, pmcid=None):
    """Tente de récupérer le PDF depuis Europe PMC."""
    if not pmid and not pmcid:
        return None, "Pas de PMID ni PMCID"
    
    try:
        # Europe PMC accepte soit PMID soit PMCID
        identifier = f"PMC{_clean_pmcid(pmcid)}" if pmcid else pmid
        eu_url = f"https://europepmc.org/api/fulltextRepo?pmid={identifier}"
        
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(eu_url, headers=headers, timeout=30)
        
        if r.status_code != 200:
            return None, f"EuropePMC: HTTP {r.status_code}"
        
        # Analyse de la réponse XML pour trouver le lien PDF
        try:
            root = ET.fromstring(r.content)
            pdf_link = root.find('.//link[@format="pdf"]')
            
            if pdf_link is not None and pdf_link.get('href'):
                pdf_url = pdf_link.get('href')
                r2 = requests.get(pdf_url, headers=headers, timeout=30)
                
                if r2.status_code == 200 and "application/pdf" in r2.headers.get("Content-Type", ""):
                    return r2.content, None
        except ET.ParseError:
            pass
        
        return None, "EuropePMC: PDF non trouvé"
    
    except Exception as e:
        return None, f"EuropePMC erreur: {e}"
        
def fetch_pdf_cascade(pmid, doi, pmcid, unpaywall_email, utiliser_scihub=False):
    """Cascade optimisée de récupération PDF."""
    # 1. PMC FTP
    if pmcid:
        pdf, err = fetch_pdf_from_pmc_ftp(pmcid)
        if pdf:
            return pdf, f"PMC FTP (PMC{_clean_pmcid(pmcid)})"
        reason_ftp = err
    else:
        reason_ftp = "Pas de PMCID"

    # 2. PMC Web
    if pmcid:
        pdf, err = fetch_pdf_from_pmc_web(pmcid)
        if pdf:
            return pdf, f"PMC Web (PMC{_clean_pmcid(pmcid)})"
        reason_web = err
    else:
        reason_web = "Pas de PMCID"

    # 3. EuropePMC
    pdf, err = fetch_pdf_from_europe_pmc(pmid, pmcid)
    if pdf:
        return pdf, "EuropePMC"
    reason_eu = err

    # 4. Unpaywall
    if doi:
        pdf, err = fetch_pdf_from_unpaywall(doi, unpaywall_email)
        if pdf:
            return pdf, "Unpaywall"
        reason_up = err
    else:
        reason_up = "Pas de DOI"

    # 5. Sci-Hub (désactivé)
    reason_sh = "Sci-Hub désactivé"

    msg = (
        f"Échec cascade PDF. "
        f"PMC FTP: {reason_ftp} | "
        f"PMC Web: {reason_web} | "
        f"EuropePMC: {reason_eu} | "
        f"Unpaywall: {reason_up} | "
        f"Sci-Hub: {reason_sh}"
    )
    return None, msg


###########################
# EXTRACTION TEXTE PDF    #
###########################

def extract_with_pymupdf(pdf_content: bytes) -> str:
    try:
        import fitz
    except ImportError:
        return ""
    try:
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        pages = min(len(doc), 20)
        return "\n\n".join(doc.load_page(i).get_text("text") for i in range(pages))
    except Exception:
        return ""


def extract_with_pdfplumber(pdf_content: bytes) -> str:
    try:
        import pdfplumber
    except ImportError:
        return ""
    try:
        with pdfplumber.open(BytesIO(pdf_content)) as pdf:
            pages = min(len(pdf.pages), 20)
            return "\n\n".join(
                pdf.pages[i].extract_text() or "" for i in range(pages)
            )
    except Exception:
        return ""


def extract_with_pypdf(pdf_content: bytes) -> str:
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
    """Essaie plusieurs moteurs successivement."""
    txt = extract_with_pymupdf(pdf_content)
    if len(txt) > 200:
        return txt, "pymupdf"

    txt = extract_with_pdfplumber(pdf_content)
    if len(txt) > 200:
        return txt, "pdfplumber"

    txt = extract_with_pypdf(pdf_content)
    if len(txt) > 200:
        return txt, "pypdf"

    return txt, "extraction_partielle"


###########################
# NOTEBOOKLM EXPORT       #
###########################

def build_notebooklm_export(meta, texte_fr: str) -> str:
    return f"""# VEILLE MEDICALE - {maintenant_str()}
Titre: {meta.get('title_fr')}
Titre original: {meta.get('title_en')}
Journal: {meta['journal']} ({meta['year']})
PMID: {meta['pmid']}
DOI: {meta.get('doi') or 'N/A'}

Texte complet traduit:
{texte_fr}
"""
###########################
# INTERFACE STREAMLIT     #
###########################

with st.sidebar:
    st.header("⚙️ Paramètres de recherche")

    st.session_state.debug = st.checkbox("Activer le mode debug", value=st.session_state.debug)

    mots_cles_fr = st.text_area("Mots-clés (FR)", "hypertension gravidique", height=80)

    if mots_cles_fr.strip():
        try:
            trad_preview = traduire_mots_cles_gemini(mots_cles_fr, G_KEY)
            st.caption("Traduction EN pour PubMed :")
            st.code(trad_preview)
        except Exception as e:
            st.warning(f"Erreur traduction mots-clés: {e}")

    date_debut = st.date_input("Date début", value=date(2024, 1, 1))
    date_fin = st.date_input("Date fin", value=date.today())

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

    utiliser_scihub = st.checkbox("Activer Sci-Hub (non implémenté)", value=False)

    lancer = st.button("🔍 Lancer la recherche", type="primary", use_container_width=True)


###########################
# LOGIQUE DE RECHERCHE    #
###########################

if lancer:
    st.session_state.articles = []
    st.session_state.details = {}

    if not mots_cles_fr.strip():
        st.error("Merci de saisir au moins un mot-clé.")
    else:
        with st.spinner("Recherche PubMed..."):
            try:
                mots_cles_en = traduire_mots_cles_gemini(mots_cles_fr, G_KEY)
                query = construire_query_pubmed(
                    mots_cles_en, date_debut, date_fin,
                    langue_code=langue_code, type_etude=type_etude
                )

                pmids = pubmed_search_ids(query, max_results=nb_max)
                meta_list = pubmed_fetch_metadata_and_abstracts(pmids)

                articles = []
                for art in meta_list:
                    # Traduction titre
                    art["title_fr"] = traduire_texte_court_cache(
                        art["title_en"], MODE_TRAD, DEEPL_KEY, G_KEY
                    )

                    # Traduction abstract
                    art["abstract_fr"] = traduire_long_texte_cache(
                        art["abstract_en"], MODE_TRAD, DEEPL_KEY, G_KEY, chunk_size=2000
                    ) if art["abstract_en"] else ""

                    articles.append(art)

                st.session_state.articles = articles

            except Exception as e:
                st.error(f"Erreur PubMed : {e}")


###########################
# AFFICHAGE DES ARTICLES  #
###########################

st.write(f"Résultats : {len(st.session_state.articles)} articles trouvés")

for art in st.session_state.articles:
    pmid = art["pmid"]

    if pmid not in st.session_state.details:
        st.session_state.details[pmid] = {
            "texte_en": None,
            "texte_fr": None,
            "source_pdf": None,
            "methode_extraction": None,
            "erreur": None,
        }

    det = st.session_state.details[pmid]

    with st.expander(f"{art['title_fr']} ({art['journal']} {art['year']}) - PMID {pmid}"):

        st.markdown(f"**Titre original (EN) :** *{art['title_en']}*")
        st.write(f"**Journal :** {art['journal']} ({art['year']})")
        st.write(f"**PMID :** {pmid}")
        st.write(f"**DOI :** {art.get('doi') or 'N/A'}")
        st.write(f"**PMCID :** {art.get('pmcid') or 'N/A'}")

        # Abstract FR
        if art["abstract_fr"]:
            st.markdown("### 🧾 Abstract (FR)")
            st.text(art["abstract_fr"])

        # Abstract EN
        if art["abstract_en"]:
            with st.expander("Voir abstract original (EN)"):
                st.text(art["abstract_en"])

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            if st.button(f"📥 Récupérer PDF + traduire (PMID {pmid})", key=f"btn_{pmid}"):

                with st.spinner("Téléchargement et extraction du PDF..."):
                    pdf_bytes, source = fetch_pdf_cascade(
                        pmid, art.get("doi"), art.get("pmcid"),
                        UNPAYWALL_EMAIL, utiliser_scihub
                    )

                    if not pdf_bytes:
                        det["erreur"] = source
                        st.error(f"Échec PDF : {source}")
                    else:
                        det["source_pdf"] = source
                        texte_en, methode = extract_text_from_pdf(pdf_bytes)
                        texte_en = nettoyer_texte_pdf(texte_en)

                        if len(texte_en) < 200:
                            det["erreur"] = "Texte extrait insuffisant"
                            st.error(det["erreur"])
                        else:
                            det["methode_extraction"] = methode
                            texte_en_tronque = tronquer(texte_en)
                            det["texte_en"] = texte_en_tronque

                            st.info("Traduction du PDF en cours...")
                            det["texte_fr"] = traduire_long_texte_cache(
                                texte_en_tronque, MODE_TRAD, DEEPL_KEY, G_KEY
                            )
                            st.success("PDF extrait et traduit avec succès")

        with col2:
            if det["texte_fr"]:
                st.write(f"**Source PDF :** {det['source_pdf']}")
                st.write(f"**Méthode extraction :** {det['methode_extraction']}")
                st.text(det["texte_fr"][:800])

                export_txt = build_notebooklm_export(art, det["texte_fr"])
                st.download_button(
                    "📥 Export NotebookLM",
                    data=export_txt,
                    file_name=f"notebooklm_pmid_{pmid}.txt",
                    mime="text/plain"
                )

            elif det["erreur"]:
                st.error(det["erreur"])
