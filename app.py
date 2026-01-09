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
import time
import tarfile

st.set_page_config(page_title="Veille Médicale Pro v5", layout="wide")

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

SOURCES_PAR_SPECIALITE = {
    "Gynécologie": {
        "CNGOF": {"url": "http://www.cngof.fr", "description": "Recommandations françaises", "recherche": "http://www.cngof.fr/?s="},
        "ACOG": {"url": "https://www.acog.org", "description": "ACOG", "recherche": "https://www.acog.org/search?q="},
        "HAS": {"url": "https://www.has-sante.fr", "description": "HAS", "recherche": "https://www.has-sante.fr/jcms/recherche?text="}
    },
    "Obstétrique": {
        "CNGOF": {"url": "http://www.cngof.fr", "description": "CNGOF", "recherche": "http://www.cngof.fr/?s="},
        "RCOG": {"url": "https://www.rcog.org.uk", "description": "RCOG", "recherche": "https://www.rcog.org.uk/search?q="}
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
if 'articles_selectionnes_export' not in st.session_state:
    st.session_state.articles_selectionnes_export = []

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
    titre = re.sub(r'\s*\(see\s+more\)\s*', '', titre, flags=re.IGNORECASE)
    titre = re.sub(r'\s*voir\s+plus\s*', '', titre, flags=re.IGNORECASE)
    titre = re.sub(r'\s+', ' ', titre)
    
    return titre.strip()

def traduire_texte(texte, mode="gemini"):
    """Traduit un texte"""
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
- Conserve la terminologie médicale exacte

TEXTE À TRADUIRE:
{texte}

TRADUCTION FRANÇAISE:"""
        
        response = model.generate_content(prompt)
        traduction = response.text.strip()
        traduction = traduction.replace("**", "")
        traduction = re.sub(r'^(Traduction\s*:?\s*)', '', traduction, flags=re.IGNORECASE)
        traduction = nettoyer_titre(traduction)
        
        return traduction
    except Exception as e:
        return texte

def traduire_mots_cles(mots_cles_fr):
    """Traduit mots-clés"""
    try:
        genai.configure(api_key=G_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        prompt = f"""Traduis ces mots-clés français en termes médicaux anglais pour PubMed.

MOTS-CLÉS FRANÇAIS:
{mots_cles_fr}

TERMES ANGLAIS:"""
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return mots_cles_fr

def get_doi_from_pubmed(pmid):
    """Récupère DOI et PMCID"""
    try:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        params = {"db": "pubmed", "id": pmid, "retmode": "xml"}
        
        response = requests.get(base_url, params=params, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            
            doi = None
            pmcid = None
            
            for article_id in root.findall('.//ArticleId'):
                id_type = article_id.get('IdType')
                if id_type == 'doi':
                    doi = article_id.text
                elif id_type == 'pmc':
                    pmcid = article_id.text
                    if pmcid.startswith('PMC'):
                        pmcid = pmcid[3:]
            
            return doi, pmcid
        
        return None, None
    except:
        return None, None

def recuperer_articles_complets(pmids, traduire_titres=False, mode_traduction="gemini"):
    """
    NOUVELLE VERSION v5: Récupère titres + RÉSUMÉS + liens PDF
    """
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", "rettype": "abstract"}
    
    try:
        response = requests.get(base_url, params=params, timeout=15)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            articles_data = []
            
            for article in root.findall('.//PubmedArticle'):
                pmid = article.find('.//PMID').text if article.find('.//PMID') is not None else "N/A"
                
                # Titre
                title_elem = article.find('.//ArticleTitle')
                if title_elem is not None:
                    title = ''.join(title_elem.itertext())
                else:
                    title = "Titre non disponible"
                
                title = nettoyer_titre(title)
                
                # NOUVEAU: Résumé
                abstract_elem = article.find('.//Abstract/AbstractText')
                if abstract_elem is not None:
                    abstract = ''.join(abstract_elem.itertext())
                else:
                    abstract = "Résumé non disponible"
                
                # Traduire titre et résumé
                if traduire_titres and title != "Titre non disponible":
                    title_fr = traduire_texte(title, mode=mode_traduction)
                    title_fr = nettoyer_titre(title_fr)
                else:
                    title_fr = title
                
                if abstract != "Résumé non disponible":
                    abstract_fr = traduire_texte(abstract[:1000], mode=mode_traduction)  # Limiter pour traduction
                else:
                    abstract_fr = abstract
                
                # Journal et date
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
                
                # NOUVEAU: Récupérer DOI et PMCID pour générer liens PDF
                doi, pmcid = get_doi_from_pubmed(pmid)
                
                # Générer liens PDF
                pdf_links = []
                if pmcid:
                    pdf_links.append({
                        "source": "PMC Open Access",
                        "url": f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/pdf/"
                    })
                if doi:
                    pdf_links.append({
                        "source": "Publisher (DOI)",
                        "url": f"https://doi.org/{doi}"
                    })
                
                articles_data.append({
                    'pmid': pmid,
                    'title': title,
                    'title_fr': title_fr,
                    'abstract': abstract,
                    'abstract_fr': abstract_fr,
                    'journal': journal,
                    'year': year,
                    'date_pub': date_pub,
                    'doi': doi,
                    'pmcid': pmcid,
                    'pdf_links': pdf_links
                })
            
            return articles_data
    except Exception as e:
        st.warning(f"Erreur: {str(e)}")
        return []
    return []

def telecharger_pdf_depuis_url(url):
    """
    NOUVEAU: Télécharge un PDF depuis une URL donnée par l'utilisateur
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        response = requests.get(url, timeout=30, headers=headers, allow_redirects=True)
        
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            
            if 'application/pdf' in content_type:
                return response.content, None
            else:
                return None, f"Le contenu n'est pas un PDF (type: {content_type})"
        else:
            return None, f"Erreur HTTP {response.status_code}"
    
    except Exception as e:
        return None, f"Erreur: {str(e)}"

def extraire_texte_pdf(pdf_content):
    """Extrait le texte d'un PDF"""
    try:
        # Essayer pdfplumber
        try:
            import pdfplumber
            pdf_file = BytesIO(pdf_content)
            with pdfplumber.open(pdf_file) as pdf:
                texte = ""
                for page in pdf.pages[:15]:  # 15 premières pages
                    texte += page.extract_text() + "\n\n"
                if len(texte) > 100:
                    return texte, "pdfplumber"
        except:
            pass
        
        # Fallback pypdf
        pdf_file = BytesIO(pdf_content)
        pdf_reader = pypdf.PdfReader(pdf_file)
        texte = ""
        for page in pdf_reader.pages[:15]:
            texte += page.extract_text() + "\n\n"
        
        return texte, "pypdf"
    
    except Exception as e:
        return "", f"Erreur: {str(e)}"

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

def generer_pdf_export(spec, periode, articles):
    """Génère PDF d'export"""
    pdf = PDF()
    pdf.add_page()
    
    pdf.set_font('Arial', 'B', 20)
    pdf.ln(30)
    pdf.cell(0, 15, 'VEILLE MEDICALE', 0, 1, 'C')
    pdf.ln(20)
    
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, f'Specialite: {spec}', 0, 1, 'C')
    pdf.cell(0, 8, f'Periode: {periode}', 0, 1, 'C')
    pdf.cell(0, 8, f'Articles: {len(articles)}', 0, 1, 'C')
    pdf.cell(0, 8, f'Date: {datetime.now().strftime("%d/%m/%Y")}', 0, 1, 'C')
    
    for i, article in enumerate(articles, 1):
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
        
        # Résumé ou texte complet
        contenu = article.get('pdf_texte_fr') or article.get('abstract_fr', '')
        if contenu and contenu != "Résumé non disponible":
            try:
                contenu_clean = contenu[:8000].encode('latin-1', 'ignore').decode('latin-1')
            except:
                contenu_clean = contenu[:8000].encode('ascii', 'ignore').decode('ascii')
            pdf.multi_cell(0, 4, contenu_clean)
    
    pdf_output = io.BytesIO()
    pdf_string = pdf.output(dest='S').encode('latin-1')
    pdf_output.write(pdf_string)
    pdf_output.seek(0)
    
    return pdf_output.getvalue()

def generer_notebooklm(articles):
    """Génère fichier NotebookLM"""
    contenu = f"""# VEILLE MEDICALE - PODCAST
Date: {datetime.now().strftime("%d/%m/%Y")}

## ARTICLES SELECTIONNES

"""
    
    for i, article in enumerate(articles, 1):
        contenu_article = article.get('pdf_texte_fr') or article.get('abstract_fr', 'Contenu non disponible')
        
        contenu += f"""
### Article {i}
Titre: {article['title_fr']}
Journal: {article['journal']} ({article['year']})
PMID: {article['pmid']}

Contenu:
{contenu_article}

---
"""
    
    return contenu

# Interface
st.title("🩺 Veille Médicale Professionnelle v5 HYBRID")

with st.expander("ℹ️ Nouveautés v5 - MODE HYBRIDE"):
    st.markdown("""
    **Approche en 2 TEMPS pour contourner les restrictions réseau:**
    
    ### 🔍 TEMPS 1: Recherche rapide (TOUJOURS fonctionnel)
    - ✅ Récupération titres + **résumés traduits**
    - ✅ Analyse IA sur les résumés
    - ✅ **Liens directs** vers PDF (PMC, DOI)
    - ⚡ Rapide et fiable
    
    ### 📄 TEMPS 2: Analyse approfondie (optionnelle)
    - 📥 **Onglet "Analyse PDF"**: Collez l'URL d'un PDF
    - 🌐 Téléchargement + traduction du PDF complet
    - 🎙️ Génération podcast NotebookLM
    - 💾 Export PDF final
    
    **Avantages:**
    - Fonctionne même avec restrictions réseau
    - Vous choisissez quels articles analyser en profondeur
    - Plus rapide pour parcourir beaucoup d'articles
    """)

if DEEPL_KEY:
    st.success("✅ DeepL Pro+ activé")
else:
    st.info("ℹ️ Traduction : Gemini 2.0 Flash")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔍 Recherche", "📄 Analyse PDF", "🔗 Sources", "⚙️ Configuration", "📚 Export"])

with tab1:
    st.header("🔍 Recherche & Résumés")
    
    with st.sidebar:
        st.header("⚙️ Paramètres")
        
        mode_recherche = st.radio("Mode", ["Par spécialité", "Par mots-clés"])
        
        if mode_recherche == "Par spécialité":
            spec_fr = st.selectbox("🏥 Spécialité", list(TRAD.keys()))
            mots_cles_custom = ""
        else:
            spec_fr = None
            mots_cles_custom = st.text_area("🔎 Mots-clés", placeholder="Ex: hypertension gravidique", height=80)
        
        st.subheader("📅 Période")
        col1, col2 = st.columns(2)
        with col1:
            date_debut = st.date_input("Début", value=date(2024, 1, 1), format="DD/MM/YYYY")
        with col2:
            date_fin = st.date_input("Fin", value=date.today(), format="DD/MM/YYYY")
        
        st.subheader("🔬 Filtres")
        langue_selectionnee = st.selectbox("Langue", list(LANGUES.keys()))
        type_etude = st.selectbox("Type", list(TYPES_ETUDE.keys()))
        nb_max = st.slider("Max résultats", 10, 100, 30, 10)
        
        mode_trad = "deepl" if DEEPL_KEY else "gemini"
        traduire_titres = st.checkbox("🌐 Traduire", value=True)
    
    if st.button("🔍 RECHERCHER", type="primary", use_container_width=True):
        
        if mode_recherche == "Par spécialité":
            term = TRAD[spec_fr]
            spec_utilisee = spec_fr
        else:
            if not mots_cles_custom:
                st.error("⚠️ Entrez des mots-clés")
                st.stop()
            term = traduire_mots_cles(mots_cles_custom)
            spec_utilisee = "Personnalisé"
        
        query_parts = [term]
        query_parts.append(f"{date_debut.strftime('%Y/%m/%d')}:{date_fin.strftime('%Y/%m/%d')}[pdat]")
        
        code_langue = LANGUES[langue_selectionnee]
        if code_langue:
            query_parts.append(f"{code_langue}[la]")
        
        if TYPES_ETUDE[type_etude]:
            query_parts.append(f"{TYPES_ETUDE[type_etude]}[ptyp]")
        
        query = " AND ".join(query_parts)
        
        st.code(query)
        
        try:
            base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": nb_max, "sort": "date"}
            
            with st.spinner("🔎 Recherche..."):
                response = requests.get(base_url, params=params, timeout=15)
            
            if response.status_code != 200:
                st.error(f"❌ Erreur {response.status_code}")
                st.stop()
            
            data = response.json()
            ids = data.get("esearchresult", {}).get("idlist", [])
            count = data.get("esearchresult", {}).get("count", "0")
            
            if not ids:
                st.warning("⚠️ Aucun article trouvé")
                st.stop()
            
            st.success(f"✅ {count} articles trouvés")
            
            with st.spinner("📄 Récupération résumés..."):
                articles = recuperer_articles_complets(ids, traduire_titres=traduire_titres, mode_traduction=mode_trad)
            
            st.session_state.articles_previsualises = articles
            st.session_state.info_recherche = {
                'spec': spec_utilisee,
                'periode': f"{date_debut.strftime('%d/%m/%Y')} - {date_fin.strftime('%d/%m/%Y')}"
            }
            
            st.rerun()
        
        except Exception as e:
            st.error(f"❌ {str(e)}")
    
    # Affichage des articles
    if st.session_state.articles_previsualises:
        st.divider()
        st.subheader("📋 Résultats")
        
        for i, article in enumerate(st.session_state.articles_previsualises):
            with st.expander(f"**{i+1}. {article['title_fr']}**"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.caption(f"📰 {article['journal']} | 📅 {article['date_pub']}")
                    
                    st.markdown("**Résumé traduit:**")
                    st.write(article['abstract_fr'])
                    
                    # Analyse IA du résumé
                    if st.button(f"🤖 Analyser résumé", key=f"analyze_{i}"):
                        with st.spinner("Analyse IA..."):
                            try:
                                genai.configure(api_key=G_KEY)
                                model = genai.GenerativeModel('gemini-2.0-flash-exp')
                                
                                prompt = f"""Analyse ce résumé médical et fournis:
- Objectif principal
- Méthodologie 
- Résultats clés
- Implications cliniques

RÉSUMÉ:
{article['abstract_fr']}

ANALYSE:"""
                                
                                response = model.generate_content(prompt)
                                st.markdown("### 🤖 Analyse")
                                st.markdown(response.text)
                            except Exception as e:
                                st.error(f"Erreur: {e}")
                
                with col2:
                    st.markdown("**Liens PDF:**")
                    st.caption(f"PMID: [{article['pmid']}](https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/)")
                    
                    for link in article['pdf_links']:
                        st.link_button(
                            f"📄 {link['source']}", 
                            link['url'],
                            use_container_width=True
                        )
                    
                    # Sélection pour export
                    if st.checkbox("📥 Export", key=f"export_{i}"):
                        if article not in st.session_state.articles_selectionnes_export:
                            st.session_state.articles_selectionnes_export.append(article)

with tab2:
    st.header("📄 Analyse Approfondie PDF")
    
    st.info("""
    **Mode d'emploi:**
    1. Recherchez vos articles dans l'onglet "Recherche"
    2. Cliquez sur un lien PDF pour l'ouvrir
    3. Copiez l'URL du PDF
    4. Collez-la ci-dessous pour analyse approfondie
    """)
    
    url_pdf = st.text_input(
        "🔗 URL du PDF",
        placeholder="https://www.ncbi.nlm.nih.gov/pmc/articles/PMC123456/pdf/...",
        help="Collez l'URL complète du PDF"
    )
    
    col_a, col_b = st.columns([2, 1])
    
    with col_a:
        pmid_assoc = st.text_input("PMID associé (optionnel)", placeholder="12345678")
    
    with col_b:
        st.write("")
        st.write("")
        analyser = st.button("🚀 ANALYSER", type="primary", use_container_width=True)
    
    if analyser and url_pdf:
        
        st.divider()
        
        # Téléchargement
        with st.spinner("📥 Téléchargement du PDF..."):
            pdf_content, erreur = telecharger_pdf_depuis_url(url_pdf)
        
        if not pdf_content:
            st.error(f"❌ {erreur}")
            st.info("💡 Essayez un autre lien PDF ou vérifiez que l'URL est correcte")
            st.stop()
        
        st.success(f"✅ PDF téléchargé ({len(pdf_content)} bytes)")
        
        # Extraction
        with st.spinner("📄 Extraction du texte..."):
            texte, methode = extraire_texte_pdf(pdf_content)
        
        if len(texte) < 100:
            st.error("❌ Impossible d'extraire le texte du PDF")
            st.stop()
        
        st.success(f"✅ Texte extrait ({len(texte)} caractères, méthode: {methode})")
        
        # Traduction
        with st.spinner("🌐 Traduction en cours..."):
            texte_traduit = ""
            chunk_size = 4000
            
            for i in range(0, min(len(texte), 12000), chunk_size):
                chunk = texte[i:i+chunk_size]
                trad = traduire_texte(chunk, mode=mode_trad)
                texte_traduit += trad + "\n\n"
        
        st.success("✅ Traduction terminée")
        
        with st.expander("📄 Lire le texte complet traduit"):
            st.text_area("Contenu", texte_traduit, height=400)
        
        # Analyse IA
        with st.spinner("🤖 Analyse IA approfondie..."):
            try:
                genai.configure(api_key=G_KEY)
                model = genai.GenerativeModel('gemini-2.0-flash-exp')
                
                prompt = f"""Analyse cet article médical complet:

CONTENU:
{texte_traduit[:8000]}

Fournis une analyse structurée:
- Objectif
- Méthodologie
- Résultats détaillés
- Implications cliniques
- Limites
- Conclusion

ANALYSE:"""
                
                response = model.generate_content(prompt)
                analyse = response.text
                
                st.markdown("### 🤖 Analyse Complète")
                st.markdown(analyse)
                
                # Sauvegarder pour export
                article_analyse = {
                    'pmid': pmid_assoc or "N/A",
                    'title_fr': "Article analysé",
                    'journal': "N/A",
                    'year': "N/A",
                    'pdf_texte_fr': texte_traduit,
                    'analyse_ia': analyse
                }
                
                if st.button("💾 Sauvegarder pour export"):
                    st.session_state.articles_selectionnes_export.append(article_analyse)
                    st.success("✅ Ajouté à l'export")
            
            except Exception as e:
                st.error(f"❌ Erreur analyse: {e}")

with tab3:
    st.header("🔗 Sources Complémentaires")
    
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
    st.header("⚙️ Configuration")
    
    st.subheader("🔄 Mode Hybride v5")
    st.markdown("""
    **Fonctionnement:**
    
    1. **Recherche** → Résumés traduits + liens PDF (TOUJOURS fonctionnel)
    2. **Analyse PDF** → Téléchargement manuel pour analyse approfondie
    3. **Export** → PDF + NotebookLM avec tous les articles sélectionnés
    
    **Pourquoi ce mode?**
    - Contourne les restrictions réseau de Streamlit Cloud
    - Vous gardez le contrôle sur quels PDF télécharger
    - Plus rapide pour parcourir beaucoup d'articles
    - Export final identique à la v3
    """)
    
    st.subheader("🌐 DeepL")
    if DEEPL_KEY:
        st.success("✅ DeepL activé")
    else:
        st.info("Mode Gemini actif (gratuit)")

with tab5:
    st.header("📚 Export Final")
    
    if not st.session_state.articles_selectionnes_export:
        st.info("Aucun article sélectionné pour l'export")
        st.markdown("""
        **Pour ajouter des articles:**
        - Onglet Recherche: Cochez "📥 Export"
        - Onglet Analyse PDF: Cliquez "💾 Sauvegarder"
        """)
    else:
        st.success(f"✅ {len(st.session_state.articles_selectionnes_export)} article(s) sélectionné(s)")
        
        for i, art in enumerate(st.session_state.articles_selectionnes_export):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"{i+1}. {art.get('title_fr', 'Article')}")
            with col2:
                if st.button("🗑️", key=f"del_{i}"):
                    st.session_state.articles_selectionnes_export.pop(i)
                    st.rerun()
        
        st.divider()
        
        if st.button("📦 GÉNÉRER EXPORTS", type="primary", use_container_width=True):
            
            with st.spinner("Génération..."):
                spec = st.session_state.info_recherche.get('spec', 'Veille')
                periode = st.session_state.info_recherche.get('periode', datetime.now().strftime('%d/%m/%Y'))
                
                pdf_export = generer_pdf_export(spec, periode, st.session_state.articles_selectionnes_export)
                notebooklm_export = generer_notebooklm(st.session_state.articles_selectionnes_export)
            
            st.success("✅ Exports générés")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.download_button(
                    "📄 Télécharger PDF",
                    pdf_export,
                    f"veille_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            
            with col2:
                st.download_button(
                    "🎙️ Télécharger NotebookLM",
                    notebooklm_export,
                    f"podcast_{datetime.now().strftime('%Y%m%d')}.txt",
                    use_container_width=True
                )
            
            st.link_button("🔗 Ouvrir NotebookLM", "https://notebooklm.google.com", use_container_width=True)

st.markdown("---")
st.caption("💊 Veille Médicale v5 HYBRID | Mode 2 temps | Gemini 2.0 Flash")
