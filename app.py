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
# UTILITAIRES GÉNÉRIQUES  #
###########################

def nettoyer_texte(texte: str) -> str:
    """Nettoyage générique du texte extrait."""
    if not texte:
        return ""
    texte = re.sub(r'\s+', ' ', texte)
    texte = texte.replace('\x00', ' ')
    return texte.strip()

def nettoyer_titre(titre: str) -> str:
    """Nettoie le titre (balises, 'See more', etc.)."""
    if not titre:
        return "Titre non disponible"
    titre = re.sub(r'<[^>]+>', '', titre)
    titre = re.sub(r'\s*see\s+more\s*', '', titre, flags=re.IGNORECASE)
    titre = re.sub(r'\s*\[see\s+more\]\s*', '', titre, flags=re.IGNORECASE)
    titre = re.sub(r'\s*`\(see\s+more\)`\s*', '', titre, flags=re.IGNORECASE)
    titre = re.sub(r'\s*voir\s+plus\s*', '', titre, flags=re.IGNORECASE)
    titre = re.sub(r'\s+', ' ', titre)
    return titre.strip()

def maintenant_str() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")

def tronquer(texte: str, max_len: int = 12000) -> str:
    if not texte:
        return texte
    if len(texte) <= max_len:
        return texte
    return texte[:max_len] + "\n\n[Texte tronqué pour analyse]"

###########################
# PUBMED : RECHERCHE      #
###########################

BASE_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

def construire_query_pubmed(mots_cles_en: str,
                            date_debut,
                            date_fin,
                            langue_code: str = "",
                            type_etude: str = "") -> str:
    """Construit la query PubMed."""
    query = mots_cles_en.strip()
    if date_debut and date_fin:
        query += f' AND ("{date_debut:%Y/%m/%d}"[Date - Publication] : "{date_fin:%Y/%m/%d}"[Date - Publication])'
    if langue_code:
        query += f' AND {langue_code}[lang]'
    if type_etude:
        query += f' AND {type_etude}[pt]'
    return query

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

def pubmed_fetch_metadata(pmids):
    """Récupère titres, journal, date, DOI, PMCID."""
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
        if title_elem is not None:
            title = ''.join(title_elem.itertext())
        else:
            title = "Titre non disponible"
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
                pmcid = aid.text  # ex: PMC1234567

        results.append({
            "pmid": pmid,
            "title": title,
            "journal": journal,
            "year": year,
            "doi": doi,
            "pmcid": pmcid
        })
    return results

###########################
# RÉCUPÉRATION PDF        #
###########################

def _clean_pmcid(pmcid):
    if not pmcid:
        return None
    pmcid = pmcid.strip()
    if pmcid.upper().startswith("PMC"):
        pmcid = pmcid[3:]
    return pmcid or None

def fetch_pdf_from_pmc_ftp(pmcid):
    pmcid_num = _clean_pmcid(pmcid)
    if not pmcid_num:
        return None, "Pas de PMCID valide"
    try:
        if len(pmcid_num) >= 7:
            dir1 = pmcid_num[-7:-4].zfill(3)
            dir2 = pmcid_num[-4:-1].zfill(3)
        else:
            dir1 = "000"
            dir2 = pmcid_num[-3:].zfill(3)

        tar_url = f"https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/{dir1}/{dir2}/PMC{pmcid_num}.tar.gz"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(tar_url, headers=headers, timeout=30)
        if r.status_code != 200:
            return None, f"PMC FTP: HTTP {r.status_code}"

        tar_file = tarfile.open(fileobj=BytesIO(r.content))
        for member in tar_file.getmembers():
            if member.name.endswith(".pdf"):
                f = tar_file.extractfile(member)
                if f:
                    return f.read(), None
        return None, "PMC FTP: aucun PDF dans l'archive"
    except Exception as e:
        return None, f"PMC FTP erreur: {e}"

def fetch_pdf_from_pmc_web(pmcid):
    pmcid_num = _clean_pmcid(pmcid)
    if not pmcid_num:
        return None, "Pas de PMCID valide"
    try:
        pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid_num}/pdf/"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(pdf_url, headers=headers, timeout=30, allow_redirects=True)
        if r.status_code == 200 and "application/pdf" in r.headers.get("Content-Type", ""):
            return r.content, None
        return None, f"PMC Web: HTTP {r.status_code}, type {r.headers.get('Content-Type', '')}"
    except Exception as e:
        return None, f"PMC Web erreur: {e}"

def fetch_pdf_from_europe_pmc(pmid, pmcid=None):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        if pmcid:
            pmcid_num = _clean_pmcid(pmcid)
            pdf_url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid=PMC{pmcid_num}&blobtype=pdf"
            r = requests.get(pdf_url, headers=headers, timeout=30)
            if r.status_code == 200 and "application/pdf" in r.headers.get("Content-Type", ""):
                return r.content, None

        api_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {"query": f"EXT_ID:{pmid}", "format": "json", "resultType": "core"}
        r = requests.get(api_url, params=params, headers=headers, timeout=30)
        if r.status_code != 200:
            return None, f"EuropePMC API HTTP {r.status_code}"

        data = r.json()
        results = data.get("resultList", {}).get("result", [])
        if not results:
            return None, "EuropePMC: pas de résultat"
        res = results[0]
        if res.get("hasPDF") == "Y":
            ext_id = res.get("id")
            pdf_url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={ext_id}&blobtype=pdf"
            r2 = requests.get(pdf_url, headers=headers, timeout=30)
            if r2.status_code == 200 and "application/pdf" in r2.headers.get("Content-Type", ""):
                return r2.content, None
        return None, "EuropePMC: PDF non disponible"
    except Exception as e:
        return None, f"EuropePMC erreur: {e}"

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
            except:
                continue
        return None, "Unpaywall: PDF non trouvé"
    except Exception as e:
        return None, f"Unpaywall erreur: {e}"

def fetch_pdf_cascade(pmid,
                      doi,
                      pmcid,
                      unpaywall_email,
                      utiliser_scihub=False):
    """
    Cascade optimisée :
    1. PMC FTP
    2. PMC Web
    3. EuropePMC
    4. Unpaywall
    Sci-Hub non implémenté par défaut.
    """
    if pmcid:
        pdf, err = fetch_pdf_from_pmc_ftp(pmcid)
        if pdf:
            return pdf, f"PMC FTP (PMC{_clean_pmcid(pmcid)})"
        reason_ftp = err or "Inconnu"
    else:
        reason_ftp = "Pas de PMCID"

    if pmcid:
        pdf, err = fetch_pdf_from_pmc_web(pmcid)
        if pdf:
            return pdf, f"PMC Web (PMC{_clean_pmcid(pmcid)})"
        reason_pmc_web = err or "Inconnu"
    else:
        reason_pmc_web = "Pas de PMCID"

    pdf, err = fetch_pdf_from_europe_pmc(pmid, pmcid)
    if pdf:
        return pdf, "EuropePMC"
    reason_eu = err or "Inconnu"

    if doi:
        pdf, err = fetch_pdf_from_unpaywall(doi, unpaywall_email)
        if pdf:
            return pdf, "Unpaywall"
        reason_up = err or "Inconnu"
    else:
        reason_up = "Pas de DOI"

    if utiliser_scihub and doi:
        reason_sh = "Sci-Hub non implémenté (choix juridique)"
    else:
        reason_sh = "Sci-Hub désactivé"

    msg = (
        f"Échec cascade PDF. "
        f"PMC FTP: {reason_ftp} | "
        f"PMC Web: {reason_pmc_web} | "
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
        import fitz  # PyMuPDF
    except ImportError:
        return ""
    texte = []
    try:
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        n = min(len(doc), 20)
        for i in range(n):
            page = doc.load_page(i)
            texte.append(page.get_text("text"))
        return "\n\n".join(texte)
    except Exception:
        return ""

def extract_with_pdfplumber(pdf_content: bytes) -> str:
    try:
        import pdfplumber
    except ImportError:
        return ""
    texte = []
    try:
        with pdfplumber.open(BytesIO(pdf_content)) as pdf:
            n = min(len(pdf.pages), 20)
            for i in range(n):
                page = pdf.pages[i]
                txt = page.extract_text()
                if txt:
                    texte.append(txt)
        return "\n\n".join(texte)
    except Exception:
        return ""

def extract_with_pypdf(pdf_content: bytes) -> str:
    try:
        pdf_reader = pypdf.PdfReader(BytesIO(pdf_content))
        texte = []
        n = min(len(pdf_reader.pages), 20)
        for i in range(n):
            page = pdf_reader.pages[i]
            try:
                txt = page.extract_text()
                if txt:
                    texte.append(txt)
            except:
                continue
        return "\n\n".join(texte)
    except Exception:
        return ""

def extract_text_from_pdf(pdf_content: bytes):
    """
    Essaie plusieurs moteurs successivement.
    Retourne (texte, méthode).
    """
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
# TRADUCTION              #
###########################

def traduire_deepl(texte: str, api_key: str) -> str:
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

def traduire_gemini(texte: str, g_key: str) -> str:
    genai.configure(api_key=g_key)
    model = genai.GenerativeModel("gemini-2.0-flash-exp")
    prompt = f"""Tu es un traducteur médical professionnel. Traduis le texte anglais suivant en français médical professionnel.

CONSIGNES STRICTES:
- Fournis UNIQUEMENT la traduction française
- Pas de préambule (pas de "Traduction:", "Voici", etc.)
- Pas de numérotation ou options multiples
- Conserve la terminologie médicale exacte
- Pas de formatage markdown (**, #, etc.)

TEXTE À TRADUIRE:
{texte}

TRADUCTION FRANÇAISE:"""
    resp = model.generate_content(prompt)
    trad = resp.text.strip()
    trad = trad.replace("**", "")
    trad = re.sub(r'^(Traduction\s*:?\s*)', '', trad, flags=re.IGNORECASE)
    trad = re.sub(r'^\d+[\.\)]\s*', '', trad)
    trad = nettoyer_titre(trad)
    return trad

def traduire_long_texte(texte: str,
                        mode: str,
                        deepl_key: str = None,
                        g_key: str = None,
                        chunk_size: int = 4000) -> str:
    texte = texte.strip()
    if not texte:
        return texte
    chunks = []
    for i in range(0, len(texte), chunk_size):
        chunks.append(texte[i:i+chunk_size])

    trad_total = []
    for chunk in chunks:
        if mode == "deepl" and deepl_key:
            t = traduire_deepl(chunk, deepl_key)
        else:
            t = traduire_gemini(chunk, g_key)
        trad_total.append(t)
    return "\n\n".join(trad_total)

def traduire_mots_cles_gemini(mots_cles_fr: str, g_key: str) -> str:
    genai.configure(api_key=g_key)
    model = genai.GenerativeModel("gemini-2.0-flash-exp")
    prompt = f"""Tu es un expert en terminologie médicale. Traduis ces mots-clés français en termes médicaux anglais optimisés pour PubMed.

CONSIGNES:
- Fournis UNIQUEMENT les termes anglais
- Pas d'explication ou préambule
- Utilise la terminologie MeSH quand possible
- Sépare les termes par des virgules

MOTS-CLÉS FRANÇAIS:
{mots_cles_fr}

TERMES ANGLAIS:"""
    resp = model.generate_content(prompt)
    return resp.text.strip()

###########################
# NOTEBOOKLM EXPORT       #
###########################

def build_notebooklm_export(meta, texte_fr: str) -> str:
    """Construit un contenu structuré simple pour NotebookLM."""
    contenu = f"""# VEILLE MEDICALE - {maintenant_str()}
Titre: {meta['title']}
Journal: {meta['journal']} ({meta['year']})
PMID: {meta['pmid']}
DOI: {meta.get('doi') or 'N/A'}

Texte complet traduit:
{texte_fr}
"""
    return contenu

###########################
# INTERFACE STREAMLIT     #
###########################

st.set_page_config(page_title="Veille Médicale Pro (Monolithique)", layout="wide")
st.title("🩺 Veille Médicale Professionnelle (version monolithique)")

# Récupération des clés
try:
    G_KEY = st.secrets["GEMINI_KEY"]
except:
    st.error("⚠️ Clé GEMINI_KEY manquante")
    st.stop()

DEEPL_KEY = st.secrets.get("DEEPL_KEY", None)
UNPAYWALL_EMAIL = st.secrets.get("UNPAYWALL_EMAIL", "example@email.com")

mode_trad = "deepl" if DEEPL_KEY else "gemini"

if "articles" not in st.session_state:
    st.session_state.articles = []
if "details" not in st.session_state:
    st.session_state.details = {}

with st.sidebar:
    st.header("⚙️ Paramètres de recherche")

    mots_cles_fr = st.text_area("Mots-clés (FR)", "hypertension gravidique", height=80)

    trad_preview = ""
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
    if langue == "Anglais uniquement":
        langue_code = "eng"
    elif langue == "Français uniquement":
        langue_code = "fre"
    else:
        langue_code = ""

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

    utiliser_scihub = st.checkbox(
        "Activer Sci-Hub (dernier recours) [non implémenté]",
        value=False
    )

    lancer = st.button("🔍 Lancer la recherche", type="primary", use_container_width=True)

if lancer:
    st.session_state.articles = []
    st.session_state.details = {}
    if not mots_cles_fr.strip():
        st.error("Merci de saisir au moins un mot-clé.")
    else:
        with st.spinner("Recherche PubMed..."):
            mots_cles_en = traduire_mots_cles_gemini(mots_cles_fr, G_KEY)
            query = construire_query_pubmed(
                mots_cles_en,
                date_debut,
                date_fin,
                langue_code=langue_code,
                type_etude=type_etude
            )
            try:
                pmids = pubmed_search_ids(query, max_results=nb_max)
                meta = pubmed_fetch_metadata(pmids)
                st.session_state.articles = meta
            except Exception as e:
                st.error(f"Erreur lors de la recherche PubMed : {e}")

st.write(f"Résultats : {len(st.session_state.articles)} articles trouvés")

for art in st.session_state.articles:
    pmid = art["pmid"]
    with st.expander(f"{art['title']} ({art['journal']} {art['year']}) - PMID {pmid}"):
        st.write(f"**Journal :** {art['journal']} ({art['year']})")
        st.write(f"**PMID :** {pmid}")
        st.write(f"**DOI :** {art.get('doi') or 'N/A'}")
        st.write(f"**PMCID :** {art.get('pmcid') or 'N/A'}")

        if pmid not in st.session_state.details:
            st.session_state.details[pmid] = {
                "texte_en": None,
                "texte_fr": None,
                "source_pdf": None,
                "methode_extraction": None,
                "erreur": None,
            }

        det = st.session_state.details[pmid]

        col1, col2 = st.columns(2)
        with col1:
            if st.button(f"📥 Récupérer PDF + traduire (PMID {pmid})", key=f"btn_{pmid}"):
                with st.spinner("Téléchargement et extraction du PDF..."):
                    pdf_bytes, source = fetch_pdf_cascade(
                        pmid,
                        art.get("doi"),
                        art.get("pmcid"),
                        UNPAYWALL_EMAIL,
                        utiliser_scihub=utiliser_scihub,
                    )
                    if not pdf_bytes:
                        det["erreur"] = source
                        st.error(f"Échec PDF : {source}")
                    else:
                        det["source_pdf"] = source
                        texte_en, methode = extract_text_from_pdf(pdf_bytes)
                        texte_en = nettoyer_texte(texte_en)
                        if len(texte_en) < 200:
                            det["erreur"] = "Texte extrait insuffisant"
                            st.error("Texte extrait insuffisant")
                        else:
                            det["methode_extraction"] = methode
                            texte_en_tronque = tronquer(texte_en, 12000)
                            det["texte_en"] = texte_en_tronque

                            st.info("Traduction en cours...")
                            try:
                                texte_fr = traduire_long_texte(
                                    texte_en_tronque,
                                    mode=mode_trad,
                                    deepl_key=DEEPL_KEY,
                                    g_key=G_KEY
                                )
                                det["texte_fr"] = texte_fr
                                st.success("PDF extrait et traduit avec succès ✅")
                            except Exception as e:
                                det["erreur"] = f"Erreur traduction: {e}"
                                st.error(det["erreur"])

        with col2:
            if det["texte_fr"]:
                st.write(f"**Source PDF :** {det['source_pdf']}")
                st.write(f"**Méthode extraction :** {det['methode_extraction']}")
                st.write("**Aperçu du texte traduit :**")
                st.text(det["texte_fr"][:800])

                export_txt = build_notebooklm_export(art, det["texte_fr"])
                st.download_button(
                    "📥 Export NotebookLM (texte structuré)",
                    data=export_txt,
                    file_name=f"notebooklm_pmid_{pmid}.txt",
                    mime="text/plain"
                )
            elif det["erreur"]:
                st.error(det["erreur"])
