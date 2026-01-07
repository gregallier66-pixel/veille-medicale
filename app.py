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

st.set_page_config(page_title="Veille Médicale Pro", layout="wide")

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
        },
        "ASA": {
            "url": "https://www.asahq.org",
            "description": "American Society of Anesthesiologists",
            "recherche": "https://www.asahq.org/search?q="
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
        }
    },
    "Médecine Générale": {
        "HAS": {
            "url": "https://www.has-sante.fr",
            "description": "Haute Autorité de Santé",
            "recherche": "https://www.has-sante.fr/jcms/recherche?text="
        },
        "CNGE": {
            "url": "https://www.cnge.fr",
            "description": "Collège National des Généralistes Enseignants",
            "recherche": "https://www.cnge.fr/?s="
        }
    },
    "Chirurgie Gynécologique": {
        "CNGOF": {
            "url": "http://www.cngof.fr",
            "description": "Recommandations chirurgie gynéco",
            "recherche": "http://www.cngof.fr/?s="
        },
        "AAGL": {
            "url": "https://www.aagl.org",
            "description": "Association for Gynecologic Laparoscopy",
            "recherche": "https://www.aagl.org/search?q="
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
        }
    }
}

# Initialiser session_state
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

def traduire_avec_deepl(texte, api_key):
    """Traduit avec DeepL API"""
    try:
        url = "https://api-free.deepl.com/v2/translate"
        
        data = {
            "auth_key": api_key,
            "text": texte,
            "target_lang": "FR",
            "source_lang": "EN",
            "formality": "more"
        }
        
        response = requests.post(url, data=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            return result["translations"][0]["text"]
        else:
            return None
    except:
        return None

def traduire_texte(texte, mode="gemini"):
    """Traduit avec DeepL ou Gemini - UNE SEULE traduction"""
    if mode == "deepl" and DEEPL_KEY:
        trad = traduire_avec_deepl(texte, DEEPL_KEY)
        if trad:
            return trad
    
    # Fallback sur Gemini
    try:
        genai.configure(api_key=G_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        prompt = f"""Traduis ce texte médical en français professionnel.
Donne UNE SEULE traduction, la plus précise et naturelle.
Ne donne PAS plusieurs options.
Ne mets PAS de numérotation ou de tirets.

Texte: {texte}

Traduction:"""
        
        response = model.generate_content(prompt)
        traduction = response.text.strip()
        
        # Nettoyer les artefacts
        traduction = traduction.replace("**", "")
        traduction = traduction.replace("Traduction:", "").strip()
        
        # Supprimer les numéros au début
        if traduction[0].isdigit():
            traduction = traduction.split(".", 1)[-1].strip()
        
        return traduction
    except:
        return texte

def nettoyer_titre(titre):
    """Nettoie le titre des balises XML et artefacts"""
    # Supprimer les balises HTML/XML
    titre = titre.replace("<i>", "").replace("</i>", "")
    titre = titre.replace("<b>", "").replace("</b>", "")
    titre = titre.replace("<sup>", "").replace("</sup>", "")
    
    # Supprimer "See more" et variantes
    titre = titre.replace("See more", "").replace("see more", "")
    titre = titre.replace("[voir plus]", "").replace("[Voir plus]", "")
    
    return titre.strip()

def get_pdf_link(pmid):
    """Récupère le lien PDF PMC - VERSION CORRIGÉE"""
    try:
        # D'abord vérifier avec elink
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
        params = {
            "dbfrom": "pubmed",
            "db": "pmc",
            "id": pmid,
            "retmode": "xml",
            "linkname": "pubmed_pmc"
        }
        
        response = requests.get(base_url, params=params, timeout=10)
        
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            
            # Chercher le PMC ID
            pmc_id = root.find('.//Link/Id')
            
            if pmc_id is not None:
                pmc_id_text = pmc_id.text
                pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id_text}/pdf/"
                return pdf_url, pmc_id_text
        
        return None, None
    except Exception as e:
        return None, None

def verifier_pdf_disponible(pmid):
    """Vérifie si le PDF est réellement accessible"""
    pdf_url, pmc_id = get_pdf_link(pmid)
    
    if not pdf_url:
        return False
    
    try:
        # Tester l'accès au PDF
        response = requests.head(pdf_url, timeout=10, allow_redirects=True)
        return response.status_code == 200
    except:
        return False

def telecharger_et_extraire_pdf(pmid, mode_traduction="gemini", progress_callback=None):
    """Télécharge, extrait et traduit le PDF - VERSION CORRIGÉE"""
    try:
        pdf_url, pmc_id = get_pdf_link(pmid)
        
        if not pdf_url:
            return None, "PDF non disponible en libre accès sur PubMed Central"
        
        if progress_callback:
            progress_callback(f"📥 Téléchargement PDF PMID {pmid}...")
        
        # Télécharger le PDF
        response = requests.get(pdf_url, timeout=30, allow_redirects=True)
        
        if response.status_code != 200:
            return None, f"PDF non accessible (erreur {response.status_code})"
        
        # Vérifier que c'est bien un PDF
        if 'application/pdf' not in response.headers.get('Content-Type', ''):
            return None, "Le fichier téléchargé n'est pas un PDF"
        
        if progress_callback:
            progress_callback(f"📄 Extraction texte PMID {pmid}...")
        
        try:
            pdf_file = BytesIO(response.content)
            pdf_reader = pypdf.PdfReader(pdf_file)
            
            texte_complet = ""
            nb_pages = len(pdf_reader.pages)
            max_pages = min(nb_pages, 15)
            
            for i in range(max_pages):
                page = pdf_reader.pages[i]
                texte_page = page.extract_text()
                texte_complet += texte_page + "\n\n"
            
            if len(texte_complet) < 100:
                return None, "PDF extrait mais contenu insuffisant"
            
            if len(texte_complet) > 12000:
                texte_complet = texte_complet[:12000] + "\n\n[PDF tronqué]"
            
            if progress_callback:
                progress_callback(f"🌐 Traduction PMID {pmid}...")
            
            # Traduire par chunks
            chunk_size = 4000
            texte_traduit = ""
            
            for i in range(0, len(texte_complet), chunk_size):
                chunk = texte_complet[i:i+chunk_size]
                trad_chunk = traduire_texte(chunk, mode=mode_traduction)
                texte_traduit += trad_chunk + "\n\n"
            
            return texte_traduit, None
            
        except Exception as e:
            return None, f"Erreur lors de l'extraction du PDF: {str(e)}"
            
    except Exception as e:
        return None, f"Erreur: {str(e)}"

def traduire_mots_cles(mots_cles_fr):
    """Traduit mots-clés"""
    try:
        genai.configure(api_key=G_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        prompt = f"""Traduis en anglais médical pour PubMed:

{mots_cles_fr}

Anglais:"""
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return mots_cles_fr

def recuperer_titres_rapides(pmids, traduire_titres=False, mode_traduction="gemini"):
    """Récupère titres, journaux et dates"""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", "rettype": "abstract"}
    
    try:
        response = requests.get(base_url, params=params, timeout=15)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            articles_data = []
            
            for article in root.findall('.//PubmedArticle'):
                pmid = article.find('.//PMID').text if article.find('.//PMID') is not None else "N/A"
                
                title_elem = article.find('.//ArticleTitle')
                title = title_elem.text if title_elem is not None else "Titre non disponible"
                
                # Nettoyer le titre
                title = nettoyer_titre(title)
                
                # UNE SEULE traduction
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

def generer_pdf_selectionne(spec, periode, articles_selectionnes):
    """Génère PDF avec articles sélectionnés"""
    pdf = PDF()
    pdf.add_page()
    
    pdf.set_font('Arial', 'B', 20)
    pdf.ln(30)
    pdf.cell(0, 15, 'VEILLE MEDICALE', 0, 1, 'C')
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
    
    pdf_output = io.BytesIO()
    pdf_string = pdf.output(dest='S').encode('latin-1')
    pdf_output.write(pdf_string)
    pdf_output.seek(0)
    
    return pdf_output.getvalue()

def generer_notebooklm_selectionne(articles_selectionnes):
    """Génère fichier NotebookLM"""
    contenu = f"""# VEILLE MEDICALE - PODCAST
Date: {datetime.now().strftime("%d/%m/%Y")}

## ARTICLES SELECTIONNES

"""
    
    for i, article in enumerate(articles_selectionnes, 1):
        contenu += f"""
### Article {i}
Titre: {article['title_fr']}
Journal: {article['journal']} ({article['year']})
PMID: {article['pmid']}

Contenu complet:
{article.get('pdf_texte_fr', 'Non disponible')}

---
"""
    
    return contenu

# Interface principale
st.title("🩺 Veille Médicale Professionnelle")

if DEEPL_KEY:
    st.success("✅ DeepL Pro+ activé")
else:
    st.info("ℹ️ Traduction : Gemini 2.0 Flash")

tab1, tab2, tab3, tab4 = st.tabs(["🔍 Recherche", "📚 Historique", "🔗 Sources", "⚙️ DeepL"])

with tab1:
    # ÉTAPE 1
    if st.session_state.mode_etape == 1:
        st.header("📋 Étape 1 : Prévisualisation")
        
        with st.sidebar:
            st.header("⚙️ Paramètres")
            
            mode_recherche = st.radio("Mode", ["Par spécialité", "Par mots-clés"])
            
            if mode_recherche == "Par spécialité":
                spec_fr = st.selectbox("🏥 Spécialité", list(TRAD.keys()))
                mots_cles_custom = ""
                
                journaux_dispo = ["Tous"] + JOURNAUX_SPECIALITE.get(spec_fr, [])
                journal_selectionne = st.selectbox("📰 Journal", journaux_dispo)
            else:
                spec_fr = None
                journal_selectionne = "Tous"
                mots_cles_custom = st.text_area("🔎 Mots-clés", height=80)
            
            st.subheader("📅 Période")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Début**")
                date_debut = st.date_input(
                    "Date début",
                    value=date(2024, 1, 1),
                    min_value=date(2000, 1, 1),
                    max_value=date.today(),
                    format="DD/MM/YYYY",
                    label_visibility="collapsed",
                    key="date_debut"
                )
            
            with col2:
                st.write("**Fin**")
                date_fin = st.date_input(
                    "Date fin",
                    value=date.today(),
                    min_value=date(2000, 1, 1),
                    max_value=date.today(),
                    format="DD/MM/YYYY",
                    label_visibility="collapsed",
                    key="date_fin"
                )
            
            st.subheader("🔬 Filtres")
            
            mode_contenu = st.radio(
                "Type:",
                ["PDF complets uniquement", "Titre + résumé", "Titre uniquement"]
            )
            
            type_etude = st.selectbox("Étude", list(TYPES_ETUDE.keys()))
            nb_max = st.slider("Max résultats", 10, 200, 50, 10)
            
            mode_trad = "deepl" if DEEPL_KEY else "gemini"
            traduire_titres = st.checkbox("🌐 Traduire titres", value=True)
        
        if st.button("🔍 LANCER", type="primary", use_container_width=True):
            
            if mode_recherche == "Par spécialité":
                term = TRAD[spec_fr]
                display_term = spec_fr
            else:
                if not mots_cles_custom:
                    st.error("⚠️ Entrez des mots-clés")
                    st.stop()
                term = traduire_mots_cles(mots_cles_custom)
                display_term = f"Mots-clés: {mots_cles_custom}"
            
            query_parts = [term]
            
            date_debut_pubmed = date_debut.strftime("%Y/%m/%d")
            date_fin_pubmed = date_fin.strftime("%Y/%m/%d")
            query_parts.append(f"{date_debut_pubmed}:{date_fin_pubmed}[pdat]")
            
            if "PDF complets" in mode_contenu:
                query_parts.append("free full text[sb]")
            
            if journal_selectionne != "Tous":
                query_parts.append(f'"{journal_selectionne}"[Journal]')
            
            if TYPES_ETUDE[type_etude]:
                query_parts.append(f"{TYPES_ETUDE[type_etude]}[ptyp]")
            
            query = " AND ".join(query_parts)
            
            base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": nb_max, "sort": "date"}
            
            try:
                with st.spinner("Recherche PubMed..."):
                    response = requests.get(base_url, params=params, timeout=15)
                
                if response.status_code != 200:
                    st.error(f"❌ Erreur: {response.status_code}")
                    st.stop()
                
                data = response.json()
                ids = data.get("esearchresult", {}).get("idlist", [])
                count = data.get("esearchresult", {}).get("count", "0")
                
                if not ids:
                    st.warning("⚠️ Aucun article trouvé")
                    st.stop()
                
                st.success(f"✅ {count} articles trouvés - Affichage de {len(ids)}")
                
                with st.spinner("Récupération des titres..."):
                    articles_preview = recuperer_titres_rapides(ids, traduire_titres=traduire_titres, mode_traduction=mode_trad)
                
                st.session_state.articles_previsualises = articles_preview
                st.session_state.info_recherche = {
                    'display_term': display_term,
                    'periode': f"du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}",
                    'spec': spec_fr if mode_recherche == "Par spécialité" else "Personnalisé",
                    'mode_contenu': mode_contenu,
                    'mode_traduction': mode_trad
                }
                
                st.session_state.mode_etape = 2
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ {str(e)}")
    
    # ÉTAPE 2
    elif st.session_state.mode_etape == 2:
        st.header("📑 Étape 2 : Sélection")
        
        if not st.session_state.articles_previsualises:
            if st.button("↩️ Retour"):
                st.session_state.mode_etape = 1
                st.rerun()
            st.stop()
        
        st.info(f"**{st.session_state.info_recherche['display_term']}** | {st.session_state.info_recherche['periode']}")
        
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("✅ Tout sélectionner"):
                for i in range(len(st.session_state.articles_previsualises)):
                    st.session_state[f"select_{i}"] = True
                st.rerun()
        
        with col_btn2:
            if st.button("↩️ Nouvelle recherche"):
                st.session_state.mode_etape = 1
                st.session_state.articles_previsualises = []
                st.session_state.analyses_individuelles = {}
                st.rerun()
        
        st.divider()
        
        articles_selectionnes = []
        
        for i, article in enumerate(st.session_state.articles_previsualises):
            col_check, col_info = st.columns([0.1, 0.9])
            
            with col_check:
                selected = st.checkbox("", key=f"select_{i}", label_visibility="collapsed")
            
            with col_info:
                st.markdown(f"**{i+1}. {article['title_fr']}**")
                st.caption(f"📰 {article['journal']} | 📅 {article['date_pub']} | PMID: {article['pmid']}")
            
            if selected:
                articles_selectionnes.append(article['pmid'])
            
            st.divider()
        
        st.markdown(f"**{len(articles_selectionnes)} sélectionné(s)**")
        
        if 0 < len(articles_selectionnes) <= 20:
            st.divider()
            
            if st.button("🚀 ANALYSER", type="primary", use_container_width=True):
                
                st.session_state.analyses_individuelles = {}
                mode_trad = st.session_state.info_recherche.get('mode_traduction', 'gemini')
                
                # ANALYSE UN PAR UN
                articles_traites = 0
                
                for idx, pmid in enumerate(articles_selectionnes):
                    st.subheader(f"📄 Article {idx+1}/{len(articles_selectionnes)} - PMID {pmid}")
                    
                    article_info = next((a for a in st.session_state.articles_previsualises if a['pmid'] == pmid), None)
                    
                    if not article_info:
                        st.error("❌ Article introuvable")
                        continue
                    
                    st.markdown(f"**{article_info['title_fr']}**")
                    
                    # Extraction et traduction PDF
                    status_box = st.empty()
                    
                    def callback(msg):
                        status_box.info(msg)
                    
                    pdf_texte_fr, erreur = telecharger_et_extraire_pdf(
                        pmid,
                        mode_traduction=mode_trad,
                        progress_callback=callback
                    )
                    
                    status_box.empty()
                    
                    if pdf_texte_fr:
                        st.success(f"✅ PDF extrait et traduit ({len(pdf_texte_fr)} caractères)")
                        
                        # AFFICHER LE PDF TRADUIT
                        with st.expander("📄 Lire le PDF complet traduit"):
                            st.text_area(
                                "Contenu:",
                                pdf_texte_fr,
                                height=400,
                                key=f"pdf_{pmid}"
                            )
                        
                        # ANALYSE IA
                        with st.spinner("Analyse IA en cours..."):
                            try:
                                genai.configure(api_key=G_KEY)
                                model = genai.GenerativeModel('gemini-2.0-flash-exp')
                                
                                prompt = f"""Analyse médicale approfondie de cet article.

Titre: {article_info['title_fr']}
Journal: {article_info['journal']} ({article_info['year']})

Contenu complet:
{pdf_texte_fr}

Rédige une analyse structurée en français:

## Objectif de l'étude
## Méthodologie
## Résultats principaux
## Implications cliniques
## Limites de l'étude
## Conclusion

Sois précis, détaillé et cite les données chiffrées."""
                                
                                response = model.generate_content(prompt)
                                analyse = response.text
                                
                                st.markdown("### 🤖 Analyse IA")
                                st.markdown(analyse)
                                
                                # SAUVEGARDER
                                st.session_state.analyses_individuelles[pmid] = {
                                    'pmid': pmid,
                                    'title': article_info['title'],
                                    'title_fr': article_info['title_fr'],
                                    'journal': article_info['journal'],
                                    'year': article_info['year'],
                                    'date_pub': article_info['date_pub'],
                                    'pdf_texte_fr': pdf_texte_fr,
                                    'analyse_ia': analyse
                                }
                                
                                articles_traites += 1
                                
                            except Exception as e:
                                st.error(f"❌ Erreur lors de l'analyse IA: {str(e)}")
                    else:
                        st.error(f"❌ {erreur}")
                        st.info("💡 Cet article n'est pas disponible en PDF libre accès. Il faut un abonnement institutionnel pour y accéder.")
                    
                    st.divider()
                
                # SÉLECTION FINALE
                if st.session_state.analyses_individuelles:
                    st.header(f"📚 Étape 3 : Sélection finale ({len(st.session_state.analyses_individuelles)} articles analysés)")
                    
                    st.info("Sélectionnez les articles à inclure dans le PDF final et le podcast NotebookLM")
                    
                    articles_finaux = []
                    
                    for pmid, data in st.session_state.analyses_individuelles.items():
                        col_check, col_info = st.columns([0.1, 0.9])
                        
                        with col_check:
                            include = st.checkbox("", key=f"final_{pmid}", value=True, label_visibility="collapsed")
                        
                        with col_info:
                            st.markdown(f"**{data['title_fr']}**")
                            st.caption(f"{data['journal']} | {data['date_pub']}")
                        
                        if include:
                            articles_finaux.append(data)
                        
                        st.divider()
                    
                    if articles_finaux:
                        st.success(f"✅ {len(articles_finaux)} article(s) pour le PDF et podcast")
                        
                        # GÉNÉRER LES FICHIERS
                        with st.spinner("Génération des fichiers..."):
                            pdf_final = generer_pdf_selectionne(
                                st.session_state.info_recherche['spec'],
                                st.session_state.info_recherche['periode'],
                                articles_finaux
                            )
                            
                            notebooklm = generer_notebooklm_selectionne(articles_finaux)
                        
                        st.divider()
                        st.subheader("📥 Téléchargements")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.download_button(
                                "📄 PDF Final",
                                pdf_final,
                                f"veille_{datetime.now().strftime('%Y%m%d')}.pdf",
                                mime="application/pdf",
                                use_container_width=True
                            )
                        
                        with col2:
                            st.download_button(
                                "🎙️ NotebookLM",
                                notebooklm,
                                f"podcast_{datetime.now().strftime('%Y%m%d')}.txt",
                                use_container_width=True
                            )
                        
                        st.link_button("🔗 Ouvrir NotebookLM", "https://notebooklm.google.com", use_container_width=True)
                        
                        if st.button("🔄 Nouvelle recherche", use_container_width=True):
                            st.session_state.mode_etape = 1
                            st.session_state.articles_previsualises = []
                            st.session_state.analyses_individuelles = {}
                            st.rerun()
                else:
                    st.warning("⚠️ Aucun article n'a pu être analysé. Les articles sélectionnés ne sont probablement pas en libre accès.")
                    
                    if st.button("↩️ Retour à la sélection"):
                        st.rerun()

with tab2:
    st.header("📚 Historique")
    st.info("Historique des recherches sauvegardées")

with tab3:
    st.header("🔗 Sources Complémentaires par Spécialité")
    
    specialite_source = st.selectbox("Choisir une spécialité:", list(SOURCES_PAR_SPECIALITE.keys()))
    
    if specialite_source:
        st.markdown(f"### Sources pour {specialite_source}")
        
        sources = SOURCES_PAR_SPECIALITE[specialite_source]
        
        for nom, info in sources.items():
            with st.expander(f"📚 {nom}"):
                st.markdown(f"**{info['description']}**")
                st.markdown(f"**URL:** {info['url']}")
                
                mots_cles = st.text_input(f"Rechercher dans {nom}:", key=f"src_{nom}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if mots_cles:
                        st.link_button("🔍 Rechercher", f"{info['recherche']}{mots_cles}")
                
                with col2:
                    st.link_button("🏠 Accueil", info['url'])

with tab4:
    st.header("⚙️ Configuration DeepL Pro+")
    
    st.markdown("""
## 🌐 Intégration DeepL Pro+

### Étape 1 : S'abonner

1. Aller sur https://www.deepl.com/pro#developer
2. Choisir **"API Pro+"** (29,99€/mois)
3. S'inscrire et ajouter une carte bancaire

### Étape 2 : Obtenir la clé API

1. Se connecter
2. Account → API Keys
3. Copier la clé

### Étape 3 : Ajouter dans Streamlit

Dans Settings → Secrets:
```toml
DEEPL_KEY = "votre-clé-ici"
```

### 💰 Tarification

- **29,99€/mois**
- **1 million caractères/mois**
- **~100 articles complets**

### 🔄 Résiliation

1. Account → Subscription
2. Cancel subscription
3. Confirmer

✅ Aucun engagement
✅ 2 clics pour résilier
    """)
    
    if DEEPL_KEY:
        st.success("✅ DeepL Pro+ configuré")
        
        if st.button("🧪 Tester"):
            test = "This is a medical article about diabetes."
            trad = traduire_avec_deepl(test, DEEPL_KEY)
            if trad:
                st.success(f"✅ Test OK!\n\n{test}\n→\n{trad}")
            else:
                st.error("❌ Erreur")
    else:
        st.warning("⚠️ DeepL non configuré - Utilisation de Gemini 2.0 Flash")

st.markdown("---")
st.caption("💊 Veille médicale | PubMed + Gemini/DeepL")
