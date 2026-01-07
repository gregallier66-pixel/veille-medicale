import streamlit as st
import google.generativeai as genai
import requests
import json
from datetime import datetime, date, timedelta
import xml.etree.ElementTree as ET
from fpdf import FPDF
import io
import PyPDF2
from io import BytesIO

st.set_page_config(page_title="Veille Médicale Pro", layout="wide")

# Récupération de la clé Gemini
try:
    G_KEY = st.secrets["GEMINI_KEY"]
except:
    st.error("⚠️ Clé GEMINI_KEY manquante dans les secrets")
    st.stop()

# Noms des mois en français
MOIS_FR = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
    5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
    9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
}

# Spécialités RÉORGANISÉES
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

# Types d'études
TYPES_ETUDE = {
    "Tous": "",
    "Essais cliniques": "Clinical Trial",
    "Méta-analyses": "Meta-Analysis",
    "Revues systématiques": "Systematic Review",
    "Études de cohorte": "Cohort Studies",
    "Études cas-témoins": "Case-Control Studies"
}

# Journaux par spécialité
JOURNAUX_SPECIALITE = {
    "Gynécologie": ["BJOG", "Obstet Gynecol", "Am J Obstet Gynecol", "Hum Reprod", "Fertil Steril", "Gynecol Surg"],
    "Obstétrique": ["BJOG", "Obstet Gynecol", "Am J Obstet Gynecol", "Ultrasound Obstet Gynecol", "J Matern Fetal Neonatal Med"],
    "Anesthésie-Réanimation": ["Anesthesiology", "Br J Anaesth", "Anesth Analg", "Intensive Care Med", "Crit Care Med"],
    "Endocrinologie": ["J Clin Endocrinol Metab", "Diabetes Care", "Eur J Endocrinol", "Endocr Rev"],
    "Médecine Générale": ["BMJ", "JAMA", "N Engl J Med", "Lancet", "Ann Intern Med"],
    "Chirurgie Gynécologique": ["Gynecol Surg", "J Minim Invasive Gynecol", "Eur J Obstet Gynecol Reprod Biol"],
    "Infertilité": ["Fertil Steril", "Hum Reprod", "Reprod Biomed Online", "J Assist Reprod Genet"],
    "Échographie Gynécologique": ["Ultrasound Obstet Gynecol", "J Ultrasound Med", "Ultrasound Q"],
    "Oncologie": ["J Clin Oncol", "Lancet Oncol", "Cancer", "JAMA Oncol", "Ann Oncol", "Gynecol Oncol"],
    "Pédiatrie": ["Pediatrics", "JAMA Pediatr", "Arch Dis Child", "J Pediatr"]
}

# SOURCES COMPLÉMENTAIRES PAR SPÉCIALITÉ
SOURCES_PAR_SPECIALITE = {
    "Gynécologie": {
        "CNGOF": {
            "url": "http://www.cngof.fr",
            "description": "Recommandations françaises en gynécologie",
            "recherche": "http://www.cngof.fr/?s="
        },
        "ACOG": {
            "url": "https://www.acog.org",
            "description": "American College of Obstetricians and Gynecologists",
            "recherche": "https://www.acog.org/search?q="
        },
        "HAS Gynéco": {
            "url": "https://www.has-sante.fr",
            "description": "Recommandations HAS en gynécologie",
            "recherche": "https://www.has-sante.fr/jcms/recherche?text="
        }
    },
    "Obstétrique": {
        "CNGOF": {
            "url": "http://www.cngof.fr",
            "description": "Recommandations françaises en obstétrique",
            "recherche": "http://www.cngof.fr/?s="
        },
        "RCOG": {
            "url": "https://www.rcog.org.uk",
            "description": "Royal College of Obstetricians and Gynaecologists",
            "recherche": "https://www.rcog.org.uk/search?q="
        }
    },
    "Anesthésie-Réanimation": {
        "SFAR": {
            "url": "https://sfar.org",
            "description": "Société Française d'Anesthésie et de Réanimation",
            "recherche": "https://sfar.org/?s="
        }
    },
    "Endocrinologie": {
        "SFE": {
            "url": "https://www.sfendocrino.org",
            "description": "Société Française d'Endocrinologie",
            "recherche": "https://www.sfendocrino.org/?s="
        }
    },
    "Médecine Générale": {
        "HAS": {
            "url": "https://www.has-sante.fr",
            "description": "Haute Autorité de Santé",
            "recherche": "https://www.has-sante.fr/jcms/recherche?text="
        }
    },
    "Chirurgie Gynécologique": {
        "CNGOF Chirurgie": {
            "url": "http://www.cngof.fr",
            "description": "Recommandations chirurgie gynéco",
            "recherche": "http://www.cngof.fr/?s="
        }
    },
    "Infertilité": {
        "ESHRE": {
            "url": "https://www.eshre.eu",
            "description": "European Society of Human Reproduction",
            "recherche": "https://www.eshre.eu/search?q="
        }
    },
    "Échographie Gynécologique": {
        "ISUOG": {
            "url": "https://www.isuog.org",
            "description": "International Society of Ultrasound in Obstetrics",
            "recherche": "https://www.isuog.org/search.html?q="
        }
    },
    "Oncologie": {
        "INCa": {
            "url": "https://www.e-cancer.fr",
            "description": "Institut National du Cancer",
            "recherche": "https://www.e-cancer.fr/Recherche?SearchText="
        }
    },
    "Pédiatrie": {
        "SFP": {
            "url": "https://www.sfpediatrie.com",
            "description": "Société Française de Pédiatrie",
            "recherche": "https://www.sfpediatrie.com/?s="
        }
    }
}

# Initialiser session_state
if 'historique' not in st.session_state:
    st.session_state.historique = []
if 'articles_courants' not in st.session_state:
    st.session_state.articles_courants = []
if 'synthese_courante' not in st.session_state:
    st.session_state.synthese_courante = ""
if 'pmids_courants' not in st.session_state:
    st.session_state.pmids_courants = []
if 'info_recherche' not in st.session_state:
    st.session_state.info_recherche = {}
if 'fichier_notebooklm' not in st.session_state:
    st.session_state.fichier_notebooklm = ""
if 'pdf_complet' not in st.session_state:
    st.session_state.pdf_complet = None
if 'script_audio_fr' not in st.session_state:
    st.session_state.script_audio_fr = ""
if 'sources_complementaires_contenu' not in st.session_state:
    st.session_state.sources_complementaires_contenu = []
if 'synthese_enrichie' not in st.session_state:
    st.session_state.synthese_enrichie = ""
if 'pdfs_extraits' not in st.session_state:
    st.session_state.pdfs_extraits = {}
if 'articles_previsualises' not in st.session_state:
    st.session_state.articles_previsualises = []
if 'mode_etape' not in st.session_state:
    st.session_state.mode_etape = 1  # 1 = prévisualisation, 2 = analyse détaillée

def get_pdf_link(pmid):
    """Récupère le lien PDF PMC"""
    try:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
        params = {
            "dbfrom": "pubmed",
            "db": "pmc",
            "id": pmid,
            "retmode": "xml"
        }
        
        response = requests.get(base_url, params=params, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            pmc_id = root.find('.//Link/Id')
            
            if pmc_id is not None:
                pmc_id_text = pmc_id.text
                pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id_text}/pdf/"
                return pdf_url, pmc_id_text
        
        return None, None
    except:
        return None, None

def telecharger_et_extraire_pdf(pmid, traduire=False, api_key=None, progress_callback=None):
    """Télécharge, extrait et optionnellement traduit le contenu d'un PDF"""
    try:
        pdf_url, pmc_id = get_pdf_link(pmid)
        
        if not pdf_url:
            return None, "PDF non disponible"
        
        if progress_callback:
            progress_callback(f"Téléchargement PDF PMID {pmid}...")
        
        response = requests.get(pdf_url, timeout=30)
        
        if response.status_code != 200:
            return None, f"Erreur téléchargement: {response.status_code}"
        
        if progress_callback:
            progress_callback(f"Extraction texte PMID {pmid}...")
        
        try:
            pdf_file = BytesIO(response.content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            texte_complet = ""
            nb_pages = len(pdf_reader.pages)
            max_pages = min(nb_pages, 20)
            
            for i in range(max_pages):
                page = pdf_reader.pages[i]
                texte_page = page.extract_text()
                texte_complet += texte_page + "\n\n"
            
            if len(texte_complet) > 15000:
                texte_complet = texte_complet[:15000] + "\n\n[PDF tronqué]"
            
            if traduire and api_key:
                if progress_callback:
                    progress_callback(f"Traduction PDF PMID {pmid}...")
                
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    chunk_size = 5000
                    texte_traduit = ""
                    
                    for i in range(0, len(texte_complet), chunk_size):
                        chunk = texte_complet[i:i+chunk_size]
                        
                        prompt_trad = f"""Traduis en français:

{chunk}

Traduction:"""
                        
                        response_trad = model.generate_content(prompt_trad)
                        texte_traduit += response_trad.text + "\n\n"
                    
                    return texte_traduit, None
                    
                except:
                    return texte_complet + "\n\n[Traduction échouée]", None
            
            return texte_complet, None
            
        except Exception as e:
            return None, f"Erreur extraction: {str(e)}"
    
    except Exception as e:
        return None, f"Erreur: {str(e)}"

def verifier_mots_cles_pubmed(mots_cles):
    """Vérifie les mots-clés dans PubMed"""
    try:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": mots_cles,
            "retmode": "json",
            "retmax": "1"
        }
        response = requests.get(base_url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            count = int(data.get("esearchresult", {}).get("count", "0"))
            return count > 0, count
        return False, 0
    except:
        return None, 0

def traduire_mots_cles(mots_cles_fr, api_key):
    """Traduit mots-clés FR vers EN"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""Traduis en anglais médical pour PubMed:

{mots_cles_fr}

Anglais:"""
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return mots_cles_fr

def traduire_texte(texte, api_key):
    """Traduit texte en français"""
    if not texte or texte == "Résumé non disponible":
        return texte
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""Traduis en français:

{texte}

Traduction:"""
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return texte

def recuperer_titres_rapides(pmids, traduire_titres=False, api_key=None):
    """Récupère UNIQUEMENT les titres, journaux et dates pour prévisualisation rapide"""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract"
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=15)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            articles_data = []
            
            for article in root.findall('.//PubmedArticle'):
                pmid = article.find('.//PMID').text if article.find('.//PMID') is not None else "N/A"
                
                title_elem = article.find('.//ArticleTitle')
                title = title_elem.text if title_elem is not None else "Titre non disponible"
                
                # Traduire le titre si demandé
                title_fr = title
                if traduire_titres and title != "Titre non disponible" and api_key:
                    title_fr = traduire_texte(title, api_key)
                
                journal_elem = article.find('.//Journal/Title')
                journal = journal_elem.text if journal_elem is not None else "Journal non disponible"
                
                year_elem = article.find('.//PubDate/Year')
                year = year_elem.text if year_elem is not None else "N/A"
                
                month_elem = article.find('.//PubDate/Month')
                month = month_elem.text if month_elem is not None else ""
                
                day_elem = article.find('.//PubDate/Day')
                day = day_elem.text if day_elem is not None else ""
                
                # Construire la date
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

def recuperer_abstracts(pmids, mode_contenu="tous", traduire=False, api_key=None):
    """Récupère les articles selon le mode choisi"""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract"
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=15)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            articles_data = []
            
            for article in root.findall('.//PubmedArticle'):
                pmid = article.find('.//PMID').text if article.find('.//PMID') is not None else "N/A"
                
                title_elem = article.find('.//ArticleTitle')
                title = title_elem.text if title_elem is not None else "Titre non disponible"
                
                # Récupérer le résumé seulement si nécessaire
                if mode_contenu in ["tous", "resume"]:
                    abstract_elem = article.find('.//AbstractText')
                    abstract = abstract_elem.text if abstract_elem is not None else "Résumé non disponible"
                else:
                    abstract = "Non récupéré (mode titre uniquement)"
                
                abstract_fr = abstract
                if traduire and abstract != "Résumé non disponible" and abstract != "Non récupéré (mode titre uniquement)" and api_key:
                    abstract_fr = traduire_texte(abstract, api_key)
                
                authors = []
                for author in article.findall('.//Author'):
                    lastname = author.find('LastName')
                    forename = author.find('ForeName')
                    if lastname is not None:
                        name = lastname.text
                        if forename is not None:
                            name = f"{forename.text} {name}"
                        authors.append(name)
                
                journal_elem = article.find('.//Journal/Title')
                journal = journal_elem.text if journal_elem is not None else "Journal non disponible"
                
                year_elem = article.find('.//PubDate/Year')
                year = year_elem.text if year_elem is not None else "N/A"
                
                articles_data.append({
                    'pmid': pmid,
                    'title': title,
                    'abstract': abstract,
                    'abstract_fr': abstract_fr,
                    'authors': authors,
                    'journal': journal,
                    'year': year,
                    'pdf_texte': None,
                    'pdf_disponible': False,
                    'pdf_traduit': False
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

def generer_pdf_complet(spec, periode, nb_articles, pmids, synthese, articles_data):
    """Génère PDF complet"""
    pdf = PDF()
    pdf.add_page()
    
    pdf.set_font('Arial', 'B', 20)
    pdf.ln(30)
    pdf.cell(0, 15, 'VEILLE MEDICALE', 0, 1, 'C')
    pdf.ln(20)
    
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, f'Specialite: {spec}', 0, 1, 'C')
    pdf.cell(0, 8, f'Periode: {periode}', 0, 1, 'C')
    pdf.cell(0, 8, f'Articles: {nb_articles}', 0, 1, 'C')
    pdf.cell(0, 8, f'Date: {datetime.now().strftime("%d/%m/%Y")}', 0, 1, 'C')
    
    pdf.add_page()
    pdf.section_title('SYNTHESE IA')
    
    try:
        synthese_clean = synthese.encode('latin-1', 'ignore').decode('latin-1')
    except:
        synthese_clean = synthese.encode('ascii', 'ignore').decode('ascii')
    
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 5, synthese_clean)
    
    pdf.add_page()
    pdf.section_title('ARTICLES')
    
    for i, article in enumerate(articles_data, 1):
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 8, f'Article {i} - PMID: {article["pmid"]}', 0, 1)
        
        pdf.set_font('Arial', '', 10)
        try:
            title_clean = article['title'].encode('latin-1', 'ignore').decode('latin-1')
        except:
            title_clean = article['title'].encode('ascii', 'ignore').decode('ascii')
        pdf.multi_cell(0, 5, title_clean)
        pdf.ln(2)
        
        if article.get('abstract_fr'):
            try:
                abstract_clean = article['abstract_fr'].encode('latin-1', 'ignore').decode('latin-1')
            except:
                abstract_clean = article['abstract_fr'].encode('ascii', 'ignore').decode('ascii')
            pdf.multi_cell(0, 4, abstract_clean)
        pdf.ln(5)
    
    pdf_output = io.BytesIO()
    pdf_string = pdf.output(dest='S').encode('latin-1')
    pdf_output.write(pdf_string)
    pdf_output.seek(0)
    
    return pdf_output.getvalue()

def generer_fichier_notebooklm(synthese, articles_data, inclure_pdfs=False):
    """Génère fichier pour NotebookLM"""
    contenu = f"""# VEILLE MEDICALE - PODCAST
Date: {datetime.now().strftime("%d/%m/%Y")}

## SYNTHESE

{synthese}

## ARTICLES

"""
    
    for i, article in enumerate(articles_data, 1):
        contenu += f"""
### Article {i}
Titre: {article['title']}
Auteurs: {', '.join(article.get('authors', [])[:5])}
Journal: {article['journal']} ({article['year']})
PMID: {article['pmid']}

"""
        
        if article.get('abstract_fr'):
            contenu += f"Resume:\n{article['abstract_fr']}\n\n"
        
        if inclure_pdfs and article.get('pdf_texte'):
            contenu += f"PDF complet:\n{article['pdf_texte'][:5000]}...\n\n"
        
        contenu += "---\n"
    
    return contenu

def sauvegarder_recherche(spec, periode, type_etude, langue, pmids, synthese, mots_cles=""):
    """Sauvegarde recherche"""
    recherche = {
        'date': datetime.now().strftime("%d/%m/%Y %H:%M"),
        'specialite': spec,
        'periode': periode,
        'type_etude': type_etude,
        'langue': langue,
        'mots_cles': mots_cles,
        'nb_articles': len(pmids),
        'pmids': pmids,
        'synthese': synthese
    }
    st.session_state.historique.insert(0, recherche)
    if len(st.session_state.historique) > 20:
        st.session_state.historique = st.session_state.historique[:20]

# Interface principale
st.title("🩺 Veille Médicale Professionnelle")
st.markdown("*Recherche avancée en 2 étapes : Prévisualisation puis Analyse détaillée*")

tab1, tab2, tab3, tab4 = st.tabs(["🔍 Recherche", "📚 Historique", "🔗 Sources", "🎙️ Podcast"])

with tab1:
    # ÉTAPE 1 : PRÉVISUALISATION
    if st.session_state.mode_etape == 1:
        st.header("📋 Étape 1 : Prévisualisation des articles")
        
        with st.sidebar:
            st.header("⚙️ Paramètres de recherche")
            
            mode_recherche = st.radio("Mode", ["Par spécialité", "Par mots-clés"])
            
            if mode_recherche == "Par spécialité":
                spec_fr = st.selectbox("🏥 Spécialité", list(TRAD.keys()))
                mots_cles_custom = ""
                
                st.subheader("📰 Journal")
                journaux_dispo = ["Tous"] + JOURNAUX_SPECIALITE.get(spec_fr, [])
                journal_selectionne = st.selectbox("Journal", journaux_dispo)
            else:
                spec_fr = None
                journal_selectionne = "Tous"
                
                mots_cles_custom = st.text_area("🔎 Mots-clés", height=80)
            
            st.subheader("🎯 Zone")
            zone_recherche = st.radio("Chercher dans:", ["Titre et résumé", "Titre uniquement", "Résumé uniquement"])
            
            st.subheader("📅 Période")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Début**")
                jour_debut = st.selectbox("Jour", range(1, 32), index=0, key="j1")
                mois_debut = st.selectbox("Mois", range(1, 13), index=0, key="m1", format_func=lambda x: MOIS_FR[x])
                annee_debut = st.selectbox("Année", range(2000, 2027), index=24, key="a1")
            
            with col2:
                st.write("**Fin**")
                jour_fin = st.selectbox("Jour", range(1, 32), index=date.today().day-1, key="j2")
                mois_fin = st.selectbox("Mois", range(1, 13), index=date.today().month-1, key="m2", format_func=lambda x: MOIS_FR[x])
                annee_fin = st.selectbox("Année", range(2000, 2027), index=26, key="a2")
            
            try:
                date_debut = date(annee_debut, mois_debut, jour_debut)
            except:
                date_debut = date(2024, 1, 1)
            
            try:
                date_fin = date(annee_fin, mois_fin, jour_fin)
            except:
                date_fin = date.today()
            
            st.subheader("🔬 Filtres")
            
            # MODE DE CONTENU - NOUVELLE OPTION
            st.markdown("**Type de contenu:**")
            mode_contenu = st.radio(
                "Récupérer:",
                ["Tous (titre + résumé + PDF si dispo)", 
                 "Titre et résumé uniquement",
                 "Titre uniquement",
                 "PDF complets uniquement"],
                help="Choisissez le niveau de détail souhaité"
            )
            
            type_etude = st.selectbox("Type d'étude", list(TYPES_ETUDE.keys()))
            langue = st.selectbox("Langue", ["Toutes", "Anglais", "Français", "Espagnol"])
            
            # Nombre MAX de résultats à prévisualiser
            nb_max = st.slider("📊 Nb max de résultats", 10, 500, 50, step=10)
            
            traduire_titres = st.checkbox("🌐 Traduire les titres en français", value=True)
        
        if st.button("🔍 LANCER LA PRÉVISUALISATION", type="primary", use_container_width=True):
            
            if mode_recherche == "Par mots-clés" and not mots_cles_custom:
                st.error("⚠️ Entrez des mots-clés")
                st.stop()
            
            if mode_recherche == "Par spécialité":
                term = TRAD[spec_fr]
                display_term = spec_fr
            else:
                with st.spinner("Traduction..."):
                    term = traduire_mots_cles(mots_cles_custom, G_KEY)
                display_term = f"Mots-clés: {mots_cles_custom}"
            
            query_parts = [term]
            
            if zone_recherche == "Titre uniquement":
                query_parts[0] = f"{query_parts[0]}[Title]"
            elif zone_recherche == "Résumé uniquement":
                query_parts[0] = f"{query_parts[0]}[Abstract]"
            
            date_debut_pubmed = date_debut.strftime("%Y/%m/%d")
            date_fin_pubmed = date_fin.strftime("%Y/%m/%d")
            query_parts.append(f"{date_debut_pubmed}:{date_fin_pubmed}[pdat]")
            
            # Filtre PDF si mode PDF uniquement
            if "PDF complets" in mode_contenu:
                query_parts.append("free full text[sb]")
            
            if journal_selectionne != "Tous":
                query_parts.append(f'"{journal_selectionne}"[Journal]')
            
            if TYPES_ETUDE[type_etude]:
                query_parts.append(f"{TYPES_ETUDE[type_etude]}[ptyp]")
            
            langue_codes = {"Anglais": "eng", "Français": "fre", "Espagnol": "spa"}
            if langue != "Toutes":
                query_parts.append(f"{langue_codes[langue]}[la]")
            
            query = " AND ".join(query_parts)
            
            base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            
            params = {
                "db": "pubmed",
                "term": query,
                "retmode": "json",
                "retmax": nb_max,
                "sort": "date"  # Tri chronologique (plus récent d'abord)
            }
            
            try:
                with st.spinner("Recherche..."):
                    response = requests.get(base_url, params=params, headers={'User-Agent': 'Streamlit'}, timeout=15)
                
                if response.status_code != 200:
                    st.error(f"❌ Erreur: {response.status_code}")
                    st.stop()
                
                data = response.json()
                search_result = data.get("esearchresult", {})
                ids = search_result.get("idlist", [])
                count = search_result.get("count", "0")
                
                if not ids:
                    st.warning("⚠️ Aucun article trouvé")
                    st.stop()
                
                st.success(f"✅ {count} articles trouvés - Affichage de {len(ids)}")
                
                with st.spinner("Récupération des titres..."):
                    articles_preview = recuperer_titres_rapides(ids, traduire_titres=traduire_titres, api_key=G_KEY)
                
                # SAUVEGARDER les articles prévisualisés
                st.session_state.articles_previsualises = articles_preview
                st.session_state.info_recherche = {
                    'display_term': display_term,
                    'periode': f"du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}",
                    'spec': spec_fr if mode_recherche == "Par spécialité" else "Personnalisé",
                    'type_etude': type_etude,
                    'langue': langue,
                    'mode_contenu': mode_contenu,
                    'zone_recherche': zone_recherche,
                    'query': query
                }
                
                # Passer à l'étape 2
                st.session_state.mode_etape = 2
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ {str(e)}")
    
    # ÉTAPE 2 : SÉLECTION ET ANALYSE
    elif st.session_state.mode_etape == 2:
        st.header("📑 Étape 2 : Sélection des articles à analyser")
        
        if not st.session_state.articles_previsualises:
            st.warning("Aucun article prévisualisé")
            if st.button("↩️ Retour à l'étape 1"):
                st.session_state.mode_etape = 1
                st.rerun()
            st.stop()
        
        st.info(f"**Recherche:** {st.session_state.info_recherche['display_term']} | **Période:** {st.session_state.info_recherche['periode']}")
        
        # AFFICHAGE DES ARTICLES AVEC SÉLECTION
        st.markdown("### 📋 Sélectionnez les articles à analyser en détail")
        
        # Bouton pour tout sélectionner/désélectionner
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        
        with col_btn1:
            if st.button("✅ Tout sélectionner"):
                for i in range(len(st.session_state.articles_previsualises)):
                    st.session_state[f"select_{i}"] = True
                st.rerun()
        
        with col_btn2:
            if st.button("❌ Tout désélectionner"):
                for i in range(len(st.session_state.articles_previsualises)):
                    st.session_state[f"select_{i}"] = False
                st.rerun()
        
        with col_btn3:
            if st.button("↩️ Nouvelle recherche"):
                st.session_state.mode_etape = 1
                st.session_state.articles_previsualises = []
                st.rerun()
        
        st.divider()
        
        # Liste des articles avec cases à cocher
        articles_selectionnes = []
        
        for i, article in enumerate(st.session_state.articles_previsualises):
            col_check, col_info = st.columns([0.1, 0.9])
            
            with col_check:
                selected = st.checkbox("", key=f"select_{i}", label_visibility="collapsed")
            
            with col_info:
                st.markdown(f"**{i+1}. {article['title_fr']}**")
                st.caption(f"📰 {article['journal']} | 📅 {article['date_pub']} | 🔗 PMID: {article['pmid']}")
            
            if selected:
                articles_selectionnes.append(article['pmid'])
            
            if i < len(st.session_state.articles_previsualises) - 1:
                st.divider()
        
        st.markdown(f"**{len(articles_selectionnes)} article(s) sélectionné(s)**")
        
        if len(articles_selectionnes) == 0:
            st.warning("⚠️ Sélectionnez au moins un article")
        elif len(articles_selectionnes) > 20:
            st.warning("⚠️ Maximum 20 articles à la fois")
        else:
            st.divider()
            
            # OPTIONS D'ANALYSE DÉTAILLÉE
            st.subheader("⚙️ Options d'analyse détaillée")
            
            col_opt1, col_opt2 = st.columns(2)
            
            with col_opt1:
                traduire_abstracts = st.checkbox("🌐 Traduire les résumés", value=True)
                
                mode_contenu_analyse = st.session_state.info_recherche['mode_contenu']
                
                if "PDF" in mode_contenu_analyse or "Tous" in mode_contenu_analyse:
                    extraire_pdfs = st.checkbox("📄 Extraire le contenu des PDF", value=False)
                    
                    if extraire_pdfs:
                        traduire_pdfs = st.checkbox("🌐 Traduire les PDF", value=True)
                    else:
                        traduire_pdfs = False
                else:
                    extraire_pdfs = False
                    traduire_pdfs = False
            
            with col_opt2:
                st.info(f"""
**Analyse de {len(articles_selectionnes)} articles**

Mode: {mode_contenu_analyse}
Traduction résumés: {'Oui' if traduire_abstracts else 'Non'}
Extraction PDF: {'Oui' if extraire_pdfs else 'Non'}
                """)
            
            # BOUTON LANCER L'ANALYSE
            if st.button("🚀 LANCER L'ANALYSE DÉTAILLÉE", type="primary", use_container_width=True):
                
                with st.spinner("📊 Analyse en cours..."):
                    
                    # Déterminer le mode de récupération
                    if "Titre uniquement" in mode_contenu_analyse:
                        mode_recup = "titre"
                    elif "Titre et résumé" in mode_contenu_analyse:
                        mode_recup = "resume"
                    else:
                        mode_recup = "tous"
                    
                    # Récupérer les détails des articles sélectionnés
                    articles_complets = recuperer_abstracts(
                        articles_selectionnes,
                        mode_contenu=mode_recup,
                        traduire=traduire_abstracts,
                        api_key=G_KEY
                    )
                    
                    # Extraction PDF si demandé
                    if extraire_pdfs:
                        st.info("📚 Extraction des PDF...")
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        pdfs_succes = 0
                        
                        for i, article in enumerate(articles_complets):
                            progress = (i + 1) / len(articles_complets)
                            progress_bar.progress(progress)
                            status_text.text(f"PDF {i+1}/{len(articles_complets)} - PMID {article['pmid']}")
                            
                            pdf_texte, erreur = telecharger_et_extraire_pdf(
                                article['pmid'],
                                traduire=traduire_pdfs,
                                api_key=G_KEY
                            )
                            
                            if pdf_texte:
                                article['pdf_texte'] = pdf_texte
                                article['pdf_disponible'] = True
                                article['pdf_traduit'] = traduire_pdfs
                                pdfs_succes += 1
                        
                        progress_bar.empty()
                        status_text.empty()
                        
                        if pdfs_succes > 0:
                            st.success(f"✅ {pdfs_succes} PDF extraits")
                    
                    # GÉNÉRATION DE LA SYNTHÈSE IA
                    st.divider()
                    st.subheader("🤖 Synthèse IA")
                    
                    with st.spinner("Génération de la synthèse..."):
                        genai.configure(api_key=G_KEY)
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        
                        contexte = ""
                        pdfs_integres = 0
                        
                        for art in articles_complets:
                            contexte += f"\n\nPMID {art['pmid']}:\n{art['title']}\n"
                            
                            if art.get('pdf_texte'):
                                contexte += f"PDF complet:\n{art['pdf_texte']}\n"
                                pdfs_integres += 1
                            elif art.get('abstract_fr'):
                                contexte += f"Résumé: {art['abstract_fr']}\n"
                        
                        liens = "\n".join([f"- https://pubmed.ncbi.nlm.nih.gov/{pmid}/" for pmid in articles_selectionnes])
                        
                        prompt = f"""Expert médical.

{len(articles_selectionnes)} articles.

Articles:
{contexte}

Synthèse française:

## Vue d'ensemble
## Résultats
## Implications
## Limites

## Sources
{liens}"""
                        
                        response_ia = model.generate_content(prompt)
                        synthese = response_ia.text
                        
                        if pdfs_integres > 0:
                            synthese = f"**📚 {pdfs_integres} PDF complets analysés**\n\n" + synthese
                        
                        st.session_state.synthese_courante = synthese
                        st.session_state.articles_courants = articles_complets
                        st.session_state.pmids_courants = articles_selectionnes
                        
                        st.markdown(synthese)
                        
                        # Génération des fichiers
                        st.session_state.fichier_notebooklm = generer_fichier_notebooklm(
                            synthese,
                            articles_complets,
                            inclure_pdfs=extraire_pdfs
                        )
                        
                        st.session_state.pdf_complet = generer_pdf_complet(
                            st.session_state.info_recherche['display_term'],
                            st.session_state.info_recherche['periode'],
                            len(articles_selectionnes),
                            articles_selectionnes,
                            synthese,
                            articles_complets
                        )
                        
                        # Section téléchargements
                        st.divider()
                        st.subheader("📥 Téléchargements")
                        
                        col_d1, col_d2, col_d3 = st.columns(3)
                        
                        with col_d1:
                            st.download_button(
                                "📥 TXT",
                                synthese,
                                f"synthese_{datetime.now().strftime('%Y%m%d')}.txt",
                                key="dl_txt_final"
                            )
                        
                        with col_d2:
                            st.download_button(
                                "📄 PDF",
                                st.session_state.pdf_complet,
                                f"veille_{datetime.now().strftime('%Y%m%d')}.pdf",
                                mime="application/pdf",
                                key="dl_pdf_final"
                            )
                        
                        with col_d3:
                            st.download_button(
                                "🎙️ NotebookLM",
                                st.session_state.fichier_notebooklm,
                                f"podcast_{datetime.now().strftime('%Y%m%d')}.txt",
                                key="dl_nlm_final"
                            )
                        
                        sauvegarder_recherche(
                            st.session_state.info_recherche['spec'],
                            st.session_state.info_recherche['periode'],
                            st.session_state.info_recherche['type_etude'],
                            st.session_state.info_recherche['langue'],
                            articles_selectionnes,
                            synthese
                        )
                        
                        st.success("✅ Analyse terminée et sauvegardée!")
                        
                        if st.button("🔄 Nouvelle recherche"):
                            st.session_state.mode_etape = 1
                            st.session_state.articles_previsualises = []
                            st.rerun()

with tab2:
    st.header("📚 Historique")
    
    if not st.session_state.historique:
        st.info("Aucune recherche")
    else:
        for rech in st.session_state.historique:
            with st.expander(f"{rech['date']} - {rech['specialite']} - {rech['nb_articles']} articles"):
                st.markdown(f"**Spécialité:** {rech['specialite']}")
                if rech.get('mots_cles'):
                    st.markdown(f"**Mots-clés:** {rech['mots_cles']}")
                st.markdown(f"**Période:** {rech['periode']}")
                st.markdown(f"**PMIDs:** {', '.join(rech['pmids'])}")
                st.divider()
                st.markdown(rech['synthese'])

with tab3:
    st.header("🔗 Sources Directes")
    
    specialite_source = st.selectbox("Spécialité:", list(SOURCES_PAR_SPECIALITE.keys()), key="spec_src")
    
    if specialite_source:
        sources_spec = SOURCES_PAR_SPECIALITE[specialite_source]
        
        for nom_source, info_source in sources_spec.items():
            with st.expander(f"📚 {nom_source}"):
                st.markdown(f"**{info_source['description']}**")
                st.markdown(f"**URL:** {info_source['url']}")
                
                mots_cles_source = st.text_input(f"Rechercher:", key=f"s_{nom_source}")
                
                col_b1, col_b2 = st.columns(2)
                
                with col_b1:
                    if mots_cles_source:
                        st.link_button("🔍 Rechercher", f"{info_source['recherche']}{mots_cles_source}")
                
                with col_b2:
                    st.link_button("🏠 Accueil", info_source['url'])

with tab4:
    st.header("🎙️ Guide Podcasts")
    
    st.markdown("""
## 🇬🇧 NotebookLM (Gratuit)

1. Télécharger fichier
2. notebooklm.google.com
3. Importer
4. "Audio Overview"
5. Télécharger MP3

✅ Gratuit illimité

---

## 🇫🇷 ElevenLabs

**Plans:**
- Starter (5$/mois): 30k caractères
- Creator (22$/mois): 100k caractères

---

## 🔍 Recherche en 2 étapes

**Étape 1:** Prévisualisation rapide
- Tous les articles trouvés
- Titres traduits
- Tri chronologique

**Étape 2:** Sélection manuelle
- Choisissez 1 à 20 articles
- Analyse détaillée
- PDF complets optionnels
    """)

st.markdown("---")
st.caption("💊 Veille médicale | PubMed + Gemini 2.5")
