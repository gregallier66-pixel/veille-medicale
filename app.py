import streamlit as st
import google.generativeai as genai
import requests
import json
from datetime import datetime, date, timedelta
import xml.etree.ElementTree as ET
from fpdf import FPDF
import io
import calendar

st.set_page_config(page_title="Veille Médicale Pro", layout="wide")

# Récupération de la clé Gemini
try:
    G_KEY = st.secrets["GEMINI_KEY"]
except:
    st.error("⚠️ Clé GEMINI_KEY manquante dans les secrets")
    st.stop()

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
        },
        "WHO Maternal Health": {
            "url": "https://www.who.int/health-topics/maternal-health",
            "description": "OMS - Santé maternelle",
            "recherche": "https://www.who.int/search?query="
        }
    },
    "Anesthésie-Réanimation": {
        "SFAR": {
            "url": "https://sfar.org",
            "description": "Société Française d'Anesthésie et de Réanimation",
            "recherche": "https://sfar.org/?s="
        },
        "ASA": {
            "url": "https://www.asahq.org",
            "description": "American Society of Anesthesiologists",
            "recherche": "https://www.asahq.org/search?q="
        },
        "SRLF": {
            "url": "https://www.srlf.org",
            "description": "Société de Réanimation de Langue Française",
            "recherche": "https://www.srlf.org/?s="
        }
    },
    "Endocrinologie": {
        "SFE": {
            "url": "https://www.sfendocrino.org",
            "description": "Société Française d'Endocrinologie",
            "recherche": "https://www.sfendocrino.org/?s="
        },
        "Endocrine Society": {
            "url": "https://www.endocrine.org",
            "description": "Guidelines endocrinologie",
            "recherche": "https://www.endocrine.org/search?q="
        },
        "ADA": {
            "url": "https://diabetes.org",
            "description": "American Diabetes Association",
            "recherche": "https://diabetes.org/search?q="
        }
    },
    "Médecine Générale": {
        "HAS": {
            "url": "https://www.has-sante.fr",
            "description": "Haute Autorité de Santé",
            "recherche": "https://www.has-sante.fr/jcms/recherche?text="
        },
        "CMGE": {
            "url": "https://www.cnge.fr",
            "description": "Collège National des Généralistes Enseignants",
            "recherche": "https://www.cnge.fr/?s="
        },
        "Vidal": {
            "url": "https://www.vidal.fr",
            "description": "Base médicamenteuse française",
            "recherche": "https://www.vidal.fr/recherche.html?q="
        }
    },
    "Chirurgie Gynécologique": {
        "CNGOF Chirurgie": {
            "url": "http://www.cngof.fr",
            "description": "Recommandations chirurgie gynéco",
            "recherche": "http://www.cngof.fr/?s="
        },
        "AAGL": {
            "url": "https://www.aagl.org",
            "description": "Association for Gynecologic Laparoscopy",
            "recherche": "https://www.aagl.org/search?q="
        },
        "SGO": {
            "url": "https://www.sgo.org",
            "description": "Society of Gynecologic Oncology",
            "recherche": "https://www.sgo.org/search?q="
        }
    },
    "Infertilité": {
        "ESHRE": {
            "url": "https://www.eshre.eu",
            "description": "European Society of Human Reproduction",
            "recherche": "https://www.eshre.eu/search?q="
        },
        "ASRM": {
            "url": "https://www.asrm.org",
            "description": "American Society for Reproductive Medicine",
            "recherche": "https://www.asrm.org/search?q="
        },
        "CNGOF Fertilité": {
            "url": "http://www.cngof.fr",
            "description": "Recommandations françaises fertilité",
            "recherche": "http://www.cngof.fr/?s="
        }
    },
    "Échographie Gynécologique": {
        "ISUOG": {
            "url": "https://www.isuog.org",
            "description": "International Society of Ultrasound in Obstetrics",
            "recherche": "https://www.isuog.org/search.html?q="
        },
        "CFEF": {
            "url": "http://www.cfef.org",
            "description": "Collège Français d'Échographie Fœtale",
            "recherche": "http://www.cfef.org/?s="
        },
        "AIUM": {
            "url": "https://www.aium.org",
            "description": "American Institute of Ultrasound in Medicine",
            "recherche": "https://www.aium.org/search?q="
        }
    },
    "Oncologie": {
        "INCa": {
            "url": "https://www.e-cancer.fr",
            "description": "Institut National du Cancer",
            "recherche": "https://www.e-cancer.fr/Recherche?SearchText="
        },
        "NCCN": {
            "url": "https://www.nccn.org",
            "description": "National Comprehensive Cancer Network",
            "recherche": "https://www.nccn.org/search?q="
        },
        "ESMO": {
            "url": "https://www.esmo.org",
            "description": "European Society for Medical Oncology",
            "recherche": "https://www.esmo.org/search?q="
        }
    },
    "Pédiatrie": {
        "SFP": {
            "url": "https://www.sfpediatrie.com",
            "description": "Société Française de Pédiatrie",
            "recherche": "https://www.sfpediatrie.com/?s="
        },
        "AAP": {
            "url": "https://www.aap.org",
            "description": "American Academy of Pediatrics",
            "recherche": "https://www.aap.org/search?q="
        },
        "WHO Child Health": {
            "url": "https://www.who.int/health-topics/child-health",
            "description": "OMS - Santé de l'enfant",
            "recherche": "https://www.who.int/search?query="
        }
    }
}

# Initialiser session_state
if 'historique' not in st.session_state:
    st.session_state.historique = []
if 'derniere_recherche' not in st.session_state:
    st.session_state.derniere_recherche = None
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
        
        prompt = f"""Traduis ces mots-clés médicaux en anglais pour PubMed.
Retourne UNIQUEMENT les termes anglais.

Français: {mots_cles_fr}

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
        
        prompt = f"""Traduis ce texte médical en français.

Texte:
{texte}

Traduction:"""
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        if "429" in str(e) or "quota" in str(e).lower():
            return f"[Quota dépassé]\n\n{texte}"
        return f"[Erreur]\n\n{texte}"

def rechercher_source_complementaire(url_recherche, mots_cles):
    """Simule une recherche sur une source complémentaire"""
    # Note: En production, ceci utiliserait web scraping ou API
    # Pour l'instant, on simule le résultat
    return f"Résultats simulés pour '{mots_cles}' sur {url_recherche}"

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

def generer_pdf_enrichi(spec, periode, synthese_pubmed, sources_complementaires, synthese_enrichie):
    """Génère PDF avec PubMed + Sources complémentaires"""
    pdf = PDF()
    pdf.add_page()
    
    pdf.set_font('Arial', 'B', 20)
    pdf.ln(30)
    pdf.cell(0, 15, 'VEILLE MEDICALE ENRICHIE', 0, 1, 'C')
    pdf.ln(10)
    
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, f'Specialite: {spec}', 0, 1, 'C')
    pdf.cell(0, 8, f'Periode: {periode}', 0, 1, 'C')
    pdf.cell(0, 8, f'Date: {datetime.now().strftime("%d/%m/%Y")}', 0, 1, 'C')
    
    # SYNTHÈSE ENRICHIE
    pdf.add_page()
    pdf.section_title('SYNTHESE ENRICHIE (PubMed + Sources)')
    
    try:
        synthese_clean = synthese_enrichie.encode('latin-1', 'ignore').decode('latin-1')
    except:
        synthese_clean = synthese_enrichie.encode('ascii', 'ignore').decode('ascii')
    
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 5, synthese_clean)
    
    # SOURCES UTILISÉES
    pdf.add_page()
    pdf.section_title('SOURCES COMPLEMENTAIRES')
    
    for source in sources_complementaires:
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 8, f'{source["nom"]}', 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 6, f'URL: {source["url"]}', 0, 1)
        pdf.ln(3)
    
    pdf_output = io.BytesIO()
    pdf_string = pdf.output(dest='S').encode('latin-1')
    pdf_output.write(pdf_string)
    pdf_output.seek(0)
    
    return pdf_output.getvalue()

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

def recuperer_abstracts(pmids, traduire=False, api_key=None):
    """Récupère résumés PubMed"""
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
                
                abstract_elem = article.find('.//AbstractText')
                abstract = abstract_elem.text if abstract_elem is not None else "Résumé non disponible"
                
                abstract_fr = abstract
                if traduire and abstract != "Résumé non disponible" and api_key:
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
                    'year': year
                })
            
            return articles_data
    except Exception as e:
        st.warning(f"Erreur: {str(e)}")
        return []
    
    return []

def generer_fichier_notebooklm(synthese, articles_data):
    """Génère fichier pour NotebookLM"""
    contenu = f"""# VEILLE MEDICALE - SYNTHESE POUR PODCAST
Date: {datetime.now().strftime("%d/%m/%Y")}

## SYNTHESE PRINCIPALE

{synthese}

## ARTICLES SOURCES

"""
    
    for i, article in enumerate(articles_data, 1):
        contenu += f"""
### Article {i}
Titre: {article['title']}
Auteurs: {', '.join(article['authors'][:5])}
Journal: {article['journal']} ({article['year']})
PMID: {article['pmid']}

Resume:
{article['abstract_fr']}

---
"""
    
    return contenu

def generer_fichier_notebooklm_enrichi(synthese_enrichie, sources):
    """Génère fichier NotebookLM avec sources complémentaires"""
    contenu = f"""# VEILLE MEDICALE ENRICHIE - SYNTHESE POUR PODCAST
Date: {datetime.now().strftime("%d/%m/%Y")}

## SYNTHESE ENRICHIE (PubMed + Sources Complémentaires)

{synthese_enrichie}

## SOURCES COMPLEMENTAIRES UTILISEES

"""
    
    for source in sources:
        contenu += f"""
### {source['nom']}
URL: {source['url']}
Type: {source['type']}

---
"""
    
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
st.markdown("*Analyse avancée des publications PubMed avec IA*")

tab1, tab2, tab3, tab4 = st.tabs(["🔍 Recherche", "📚 Historique", "🔗 Sources Directes", "🎙️ Guide Podcast"])

with tab1:
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        mode_recherche = st.radio("Mode", ["Par spécialité", "Par mots-clés"], horizontal=True)
        
        if mode_recherche == "Par spécialité":
            spec_fr = st.selectbox("🏥 Spécialité", list(TRAD.keys()))
            mots_cles_custom = ""
            mots_cles_originaux = ""
            
            st.subheader("📰 Journal")
            journaux_dispo = ["Tous"] + JOURNAUX_SPECIALITE.get(spec_fr, [])
            journal_selectionne = st.selectbox("Journal", journaux_dispo)
            
        else:
            spec_fr = None
            journal_selectionne = "Tous"
            
            inclure_specialite = st.checkbox("🔬 Inclure spécialité", value=False)
            if inclure_specialite:
                spec_combo = st.selectbox("Spécialité", list(TRAD.keys()))
            else:
                spec_combo = None
            
            mots_cles_custom = st.text_area(
                "🔎 Mots-clés",
                placeholder="Ex: diabète gestationnel",
                height=80
            )
            mots_cles_originaux = mots_cles_custom
            
            if mots_cles_custom:
                if st.button("🔍 Vérifier"):
                    with st.spinner("Vérification..."):
                        mots_cles_en = traduire_mots_cles(mots_cles_custom, G_KEY)
                        existe, count = verifier_mots_cles_pubmed(mots_cles_en)
                        
                        if existe:
                            st.success(f"✅ {count:,} articles")
                        else:
                            st.warning("⚠️ Aucun article")
        
        st.subheader("🎯 Zone")
        zone_recherche = st.radio(
            "Chercher dans:",
            ["Titre et résumé", "Titre uniquement", "Résumé uniquement"]
        )
        
        # Sélecteurs à rouleau pour les dates
        st.subheader("📅 Période")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Date de début**")
            jour_debut = st.selectbox("Jour", range(1, 32), index=0, key="jour_debut")
            mois_debut = st.selectbox("Mois", range(1, 13), index=0, key="mois_debut", 
                                     format_func=lambda x: calendar.month_name[x])
            annee_debut = st.selectbox("Année", range(2000, 2027), index=24, key="annee_debut")
        
        with col2:
            st.write("**Date de fin**")
            jour_fin = st.selectbox("Jour", range(1, 32), index=date.today().day-1, key="jour_fin")
            mois_fin = st.selectbox("Mois", range(1, 13), index=date.today().month-1, key="mois_fin",
                                   format_func=lambda x: calendar.month_name[x])
            annee_fin = st.selectbox("Année", range(2000, 2027), index=26, key="annee_fin")
        
        # Créer les objets date
        try:
            date_debut = date(annee_debut, mois_debut, jour_debut)
        except:
            st.error("⚠️ Date de début invalide")
            date_debut = date(2024, 1, 1)
        
        try:
            date_fin = date(annee_fin, mois_fin, jour_fin)
        except:
            st.error("⚠️ Date de fin invalide")
            date_fin = date.today()
        
        if date_debut > date_fin:
            st.error("⚠️ La date de début doit être avant la date de fin")
        
        st.subheader("🔓 Accès")
        acces_libre = st.checkbox("📖 PDF gratuit uniquement", value=False)
        
        st.subheader("🔬 Filtres")
        type_etude = st.selectbox("Type", list(TYPES_ETUDE.keys()))
        
        langue = st.selectbox("Langue", [
            "Toutes",
            "Anglais",
            "Français",
            "Espagnol"
        ])
        
        traduire_abstracts = st.checkbox("🌐 Traduire", value=True)
        
        nb = st.slider("📊 Articles", 1, 20, 5)

    if st.button("🔍 Lancer", type="primary", use_container_width=True):
        
        if mode_recherche == "Par mots-clés" and not mots_cles_custom:
            st.error("⚠️ Entrez des mots-clés")
            st.stop()
        
        if date_debut > date_fin:
            st.error("⚠️ Période invalide")
            st.stop()
        
        if mode_recherche == "Par spécialité":
            term = TRAD[spec_fr]
            display_term = spec_fr
        else:
            with st.spinner("🌐 Traduction..."):
                term = traduire_mots_cles(mots_cles_custom, G_KEY)
            
            if inclure_specialite and spec_combo:
                term = f"{term} AND {TRAD[spec_combo]}"
            
            display_term = f"Mots-clés: {mots_cles_custom}"
            st.info(f"🔄 {term}")
        
        query_parts = [term]
        
        if zone_recherche == "Titre uniquement":
            query_parts[0] = f"{query_parts[0]}[Title]"
        elif zone_recherche == "Résumé uniquement":
            query_parts[0] = f"{query_parts[0]}[Abstract]"
        
        date_debut_pubmed = date_debut.strftime("%Y/%m/%d")
        date_fin_pubmed = date_fin.strftime("%Y/%m/%d")
        query_parts.append(f"{date_debut_pubmed}:{date_fin_pubmed}[pdat]")
        
        if acces_libre:
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
            "retmax": nb,
            "sort": "relevance"
        }
        
        periode_affichage = f"du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}"
        
        try:
            with st.spinner("🔎 Recherche..."):
                response = requests.get(
                    base_url,
                    params=params,
                    headers={'User-Agent': 'Streamlit App'},
                    timeout=15
                )
            
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
            
            st.success(f"✅ {count} articles - Affichage de {len(ids)}")
            
            with st.spinner("📄 Récupération..."):
                articles_complets = recuperer_abstracts(ids, traduire=traduire_abstracts, api_key=G_KEY)
            
            # SAUVEGARDER dans session_state
            st.session_state.articles_courants = articles_complets
            st.session_state.pmids_courants = ids
            st.session_state.info_recherche = {
                'display_term': display_term,
                'periode': periode_affichage,
                'spec': spec_fr if mode_recherche == "Par spécialité" else "Personnalisé",
                'type_etude': type_etude,
                'langue': langue,
                'mots_cles': mots_cles_originaux,
                'acces_libre': acces_libre,
                'specialite_originale': spec_fr
            }
            
            if articles_complets:
                st.subheader("📚 Articles")
                
                for i, article in enumerate(articles_complets, 1):
                    with st.expander(f"Article {i} - {article['title'][:80]}..."):
                        st.markdown(f"**PMID:** [{article['pmid']}](https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/)")
                        st.markdown(f"**Journal:** {article['journal']} ({article['year']})")
                        
                        if traduire_abstracts:
                            st.markdown("**📖 Résumé (FR):**")
                            st.write(article['abstract_fr'])
                        else:
                            st.markdown("**📖 Résumé:**")
                            st.write(article['abstract'])
                        
                        if acces_libre:
                            st.divider()
                            pdf_url, pmc_id = get_pdf_link(article['pmid'])
                            
                            if pdf_url:
                                st.markdown("**📄 PDF disponible**")
                                st.link_button("📥 Accéder au PDF", pdf_url)
                            else:
                                st.info("PDF non disponible")
            
            st.divider()
            st.subheader("🤖 Synthèse IA")
            
            with st.spinner("⏳ Analyse..."):
                try:
                    genai.configure(api_key=G_KEY)
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    contexte = ""
                    if articles_complets:
                        for art in articles_complets:
                            resume = art['abstract_fr'] if traduire_abstracts else art['abstract']
                            contexte += f"\n\nPMID {art['pmid']}:\n{art['title']}\n{resume}\n"
                    
                    liens = "\n".join([f"- https://pubmed.ncbi.nlm.nih.gov/{pmid}/" for pmid in ids])
                    
                    spec_texte = spec_fr if mode_recherche == "Par spécialité" else f"Mots-clés: {mots_cles_custom}"
                    
                    prompt = f"""Expert médical - Veille.

{len(ids)} articles PubMed.

Critères: {spec_texte} | {periode_affichage} | {type_etude}

Articles:
{contexte}

PMIDs: {', '.join(ids)}

Synthèse française:

## Vue ensemble
## Tendances
## Découvertes
## Implications
## Limites

## Sources
{liens}"""
                    
                    response_ia = model.generate_content(prompt)
                    synthese = response_ia.text
                    
                    # SAUVEGARDER la synthèse
                    st.session_state.synthese_courante = synthese
                    
                    st.markdown(synthese)
                    
                    # OPTION: Enrichir avec sources complémentaires
                    st.divider()
                    st.subheader("🔗 Enrichir avec Sources Complémentaires")
                    
                    specialite_recherche = spec_fr if mode_recherche == "Par spécialité" else None
                    
                    if specialite_recherche and specialite_recherche in SOURCES_PAR_SPECIALITE:
                        st.info(f"Sources disponibles pour {specialite_recherche}")
                        
                        sources_dispo = SOURCES_PAR_SPECIALITE[specialite_recherche]
                        sources_selectionnees = st.multiselect(
                            "Sélectionnez les sources à inclure:",
                            list(sources_dispo.keys()),
                            help="Les informations de ces sources seront ajoutées à votre synthèse"
                        )
                        
                        if sources_selectionnees:
                            if st.button("📚 Enrichir la synthèse", type="secondary"):
                                with st.spinner("Enrichissement avec sources complémentaires..."):
                                    # Préparer les sources
                                    sources_info = []
                                    for source_nom in sources_selectionnees:
                                        source = sources_dispo[source_nom]
                                        sources_info.append({
                                            'nom': source_nom,
                                            'url': source['url'],
                                            'type': 'Recommandations officielles',
                                            'description': source['description']
                                        })
                                    
                                    st.session_state.sources_complementaires_contenu = sources_info
                                    
                                    # Générer synthèse enrichie
                                    sources_text = "\n\n".join([
                                        f"**{s['nom']}** ({s['url']}): {s['description']}"
                                        for s in sources_info
                                    ])
                                    
                                    prompt_enrichi = f"""Tu es un expert médical. Enrichis cette synthèse PubMed avec les sources complémentaires.

**SYNTHESE PUBMED:**
{synthese}

**SOURCES COMPLEMENTAIRES A INTEGRER:**
{sources_text}

CONSIGNES:
1. Crée une synthèse ENRICHIE qui combine intelligemment:
   - Les données PubMed (recherche scientifique)
   - Les recommandations officielles des sources complémentaires
2. Structure:
   ## Vue d'ensemble enrichie
   ## Recherche récente (PubMed)
   ## Recommandations officielles (Sources complémentaires)
   ## Convergences et divergences
   ## Implications pratiques
3. Cite clairement les sources (PubMed vs Recommandations)
4. Mets en avant les points de consensus
5. Signale les divergences s'il y en a

SYNTHESE ENRICHIE:"""
                                    
                                    response_enrichi = model.generate_content(prompt_enrichi)
                                    st.session_state.synthese_enrichie = response_enrichi.text
                                    
                                    st.success("✅ Synthèse enrichie générée!")
                                    st.markdown("### 📊 Synthèse Enrichie")
                                    st.markdown(st.session_state.synthese_enrichie)
                                    
                                    # Générer fichiers enrichis
                                    fichier_nlm_enrichi = generer_fichier_notebooklm_enrichi(
                                        st.session_state.synthese_enrichie,
                                        sources_info
                                    )
                                    
                                    pdf_enrichi = generer_pdf_enrichi(
                                        display_term,
                                        periode_affichage,
                                        synthese,
                                        sources_info,
                                        st.session_state.synthese_enrichie
                                    )
                                    
                                    st.divider()
                                    st.markdown("### 📥 Téléchargements Enrichis")
                                    
                                    col_e1, col_e2, col_e3 = st.columns(3)
                                    
                                    with col_e1:
                                        st.download_button(
                                            label="📥 TXT Enrichi",
                                            data=st.session_state.synthese_enrichie,
                                            file_name="synthese_enrichie.txt",
                                            mime="text/plain",
                                            key="dl_txt_enrichi"
                                        )
                                    
                                    with col_e2:
                                        st.download_button(
                                            label="📄 PDF Enrichi",
                                            data=pdf_enrichi,
                                            file_name="veille_enrichie.pdf",
                                            mime="application/pdf",
                                            key="dl_pdf_enrichi"
                                        )
                                    
                                    with col_e3:
                                        st.download_button(
                                            label="🎙️ NotebookLM Enrichi",
                                            data=fichier_nlm_enrichi,
                                            file_name="notebooklm_enrichi.txt",
                                            mime="text/plain",
                                            key="dl_nlm_enrichi"
                                        )
                    else:
                        st.warning("Aucune source complémentaire pour cette recherche")
                    
                    # GÉNÉRER et SAUVEGARDER les fichiers standard
                    st.session_state.fichier_notebooklm = generer_fichier_notebooklm(synthese, articles_complets)
                    st.session_state.pdf_complet = generer_pdf_complet(
                        display_term,
                        periode_affichage,
                        len(ids),
                        ids,
                        synthese,
                        articles_complets
                    )
                    
                    # Section Podcast
                    st.divider()
                    st.subheader("🎙️ Générer un Podcast")
                    
                    col_podcast1, col_podcast2 = st.columns(2)
                    
                    with col_podcast1:
                        st.markdown("### 🇬🇧 NotebookLM (Anglais)")
                        st.info("Podcast conversationnel automatique")
                        
                        st.download_button(
                            label="📥 Fichier NotebookLM",
                            data=st.session_state.fichier_notebooklm,
                            file_name=f"notebooklm_{datetime.now().strftime('%Y%m%d')}.txt",
                            mime="text/plain",
                            key="download_notebooklm"
                        )
                        
                        st.link_button(
                            label="🔗 Ouvrir NotebookLM",
                            url="https://notebooklm.google.com"
                        )
                    
                    with col_podcast2:
                        st.markdown("### 🇫🇷 Script Français")
                        st.info("Script optimisé pour audio français")
                        
                        if st.button("📝 Générer Script Français", type="secondary"):
                            with st.spinner("Création script..."):
                                try:
                                    prompt_audio = f"""Producteur podcast médical français.

Synthèse:
{synthese}

Crée un SCRIPT AUDIO 10 minutes.

Format:

[GÉNÉRIQUE]

DR. MARIE: [texte]

DR. THOMAS: [texte]

Style naturel, ~1500 mots.

SCRIPT:"""
                                    
                                    response_script = model.generate_content(prompt_audio)
                                    st.session_state.script_audio_fr = response_script.text
                                    
                                except Exception as e:
                                    st.error(f"❌ {str(e)}")
                    
                    if st.session_state.script_audio_fr:
                        st.divider()
                        st.markdown("### 📜 Script Audio")
                        
                        st.text_area(
                            "Script:",
                            st.session_state.script_audio_fr,
                            height=300,
                            key="display_script"
                        )
                        
                        col_s1, col_s2 = st.columns(2)
                        
                        with col_s1:
                            st.download_button(
                                label="📥 Script",
                                data=st.session_state.script_audio_fr,
                                file_name=f"script_{datetime.now().strftime('%Y%m%d')}.txt",
                                mime="text/plain",
                                key="download_script"
                            )
                        
                        with col_s2:
                            st.link_button(
                                label="🎤 ElevenLabs",
                                url="https://elevenlabs.io"
                            )
                    
                    sauvegarder_recherche(
                        spec_fr if mode_recherche == "Par spécialité" else "Personnalisé",
                        periode_affichage,
                        type_etude,
                        langue,
                        ids,
                        synthese,
                        mots_cles_originaux
                    )
                    
                    st.success("✅ Sauvegardé")
                    
                    st.divider()
                    st.markdown("### 📥 Téléchargements Standards")
                    col1, col2 = st.columns(2)
                    
                    nom = spec_fr if mode_recherche == "Par spécialité" else "recherche"
                    
                    with col1:
                        st.download_button(
                            label="📥 TXT",
                            data=synthese,
                            file_name=f"synthese_{nom}.txt",
                            mime="text/plain",
                            key="download_txt"
                        )
                    
                    with col2:
                        st.download_button(
                            label="📄 PDF",
                            data=st.session_state.pdf_complet,
                            file_name=f"veille_{nom}.pdf",
                            mime="application/pdf",
                            key="download_pdf"
                        )
                    
                except Exception as e:
                    st.error(f"❌ {str(e)}")
        
        except Exception as e:
            st.error(f"❌ {str(e)}")

with tab2:
    st.header("📚 Historique")
    
    if not st.session_state.historique:
        st.info("Aucune recherche")
    else:
        for i, rech in enumerate(st.session_state.historique):
            titre = f"{rech['date']} - {rech['specialite']} - {rech['nb_articles']} articles"
            
            with st.expander(titre):
                st.markdown(f"**Spécialité:** {rech['specialite']}")
                if rech.get('mots_cles'):
                    st.markdown(f"**Mots-clés:** {rech['mots_cles']}")
                st.markdown(f"**Période:** {rech['periode']}")
                st.markdown(f"**PMIDs:** {', '.join(rech['pmids'])}")
                
                st.divider()
                st.markdown(rech['synthese'])

with tab3:
    st.header("🔗 Recherche Directe sur Sources Complémentaires")
    
    st.info("Recherchez directement sur les sites de référence sans passer par PubMed")
    
    # Sélection spécialité
    specialite_source = st.selectbox(
        "Choisissez une spécialité:",
        list(SOURCES_PAR_SPECIALITE.keys()),
        key="spec_source_directe"
    )
    
    if specialite_source:
        sources_spec = SOURCES_PAR_SPECIALITE[specialite_source]
        
        st.markdown(f"### Sources disponibles pour {specialite_source}")
        
        for nom_source, info_source in sources_spec.items():
            with st.expander(f"📚 {nom_source}"):
                st.markdown(f"**Description:** {info_source['description']}")
                st.markdown(f"**URL:** {info_source['url']}")
                
                # Formulaire de recherche
                mots_cles_source = st.text_input(
                    f"Rechercher dans {nom_source}:",
                    key=f"search_{nom_source}",
                    placeholder="Ex: hypertension grossesse"
                )
                
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    if mots_cles_source:
                        url_recherche = f"{info_source['recherche']}{mots_cles_source}"
                        st.link_button(
                            f"🔍 Rechercher sur {nom_source}",
                            url_recherche
                        )
                
                with col_btn2:
                    st.link_button(
                        f"🏠 Accueil {nom_source}",
                        info_source['url']
                    )

with tab4:
    st.header("🎙️ Guide Complet : Créer vos Podcasts")
    
    st.markdown("""
## 🇬🇧 Option 1 : NotebookLM (Anglais - Gratuit)

### Étapes :
1. Télécharger le fichier NotebookLM
2. Ouvrir notebooklm.google.com
3. Créer un nouveau notebook
4. Importer votre fichier
5. Cliquer sur "Audio Overview"
6. Télécharger le MP3

✅ Gratuit et illimité
✅ Qualité exceptionnelle

---

## 🇫🇷 Option 2 : ElevenLabs (Français)

### Plans:
- **Gratuit**: 10 000 caractères/mois (~7 min)
- **Starter (5$/mois)**: 30 000 caractères (~3-4 podcasts)
- **Creator (22$/mois)**: 100 000 caractères (~10 podcasts)

### Étapes:
1. Générer script français dans l'app
2. Créer compte sur elevenlabs.io
3. Coller le script
4. Choisir voix française
5. Générer et télécharger

---

## 💡 Recommandation

**Usage régulier:** NotebookLM (anglais) + ElevenLabs Starter (5$/mois) pour synthèses importantes en français
    """)

st.markdown("---")
st.caption("💊 Veille médicale | PubMed + Gemini 2.5")
