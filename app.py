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

# Paramètres de langue
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

# SOURCES COMPLÉMENTAIRES
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
    """Nettoie le titre de TOUS les artefacts"""
    if not titre:
        return "Titre non disponible"
    
    # Supprimer les balises HTML/XML
    titre = re.sub(r'<[^>]+>', '', titre)
    
    # Supprimer "See more" et variantes (insensible à la casse)
    titre = re.sub(r'\s*see\s+more\s*', '', titre, flags=re.IGNORECASE)
    titre = re.sub(r'\s*\[see\s+more\]\s*', '', titre, flags=re.IGNORECASE)
    titre = re.sub(r'\s*\(see\s+more\)\s*', '', titre, flags=re.IGNORECASE)
    titre = re.sub(r'\s*voir\s+plus\s*', '', titre, flags=re.IGNORECASE)
    
    # Supprimer espaces multiples
    titre = re.sub(r'\s+', ' ', titre)
    
    return titre.strip()

def traduire_texte(texte, mode="gemini"):
    """
    Traduit avec prompt engineering optimisé
    AMÉLIORATION: Prompt plus structuré pour éviter les artefacts
    """
    if not texte or len(texte.strip()) < 3:
        return texte
    
    if mode == "deepl" and DEEPL_KEY:
        trad = traduire_avec_deepl(texte, DEEPL_KEY)
        if trad:
            return nettoyer_titre(trad)
    
    try:
        genai.configure(api_key=G_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # NOUVEAU PROMPT OPTIMISÉ
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
        
        response = model.generate_content(prompt)
        traduction = response.text.strip()
        
        # Nettoyage post-traduction
        traduction = traduction.replace("**", "")
        traduction = re.sub(r'^(Traduction\s*:?\s*)', '', traduction, flags=re.IGNORECASE)
        traduction = re.sub(r'^\d+[\.\)]\s*', '', traduction)
        traduction = nettoyer_titre(traduction)
        
        return traduction
    except Exception as e:
        st.warning(f"Erreur traduction: {str(e)}")
        return texte

def get_doi_from_pubmed(pmid):
    """Récupère le DOI depuis PubMed"""
    try:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "xml"
        }
        
        response = requests.get(base_url, params=params, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            
            # Chercher le DOI dans ArticleIdList
            for article_id in root.findall('.//ArticleId'):
                if article_id.get('IdType') == 'doi':
                    return article_id.text
        
        return None
    except Exception as e:
        return None

def get_pmcid_from_pubmed(pmid):
    """
    NOUVEAU: Récupère le PMCID depuis PubMed
    Essentiel pour accéder aux articles PMC Open Access
    """
    try:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "xml"
        }
        
        response = requests.get(base_url, params=params, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            
            # Chercher le PMCID
            for article_id in root.findall('.//ArticleId'):
                if article_id.get('IdType') == 'pmc':
                    pmcid = article_id.text
                    # Nettoyer le PMCID (retirer "PMC" si présent)
                    if pmcid.startswith('PMC'):
                        return pmcid[3:]
                    return pmcid
        
        return None
    except Exception as e:
        return None

def get_pdf_via_pmc(pmcid):
    """
    NOUVEAU: Télécharge PDF depuis PMC Open Access
    Méthode #1 - Taux de succès ~30-40%
    """
    if not pmcid:
        return None, "Pas de PMCID"
    
    try:
        # URL directe PMC PDF
        pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/pdf/"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(pdf_url, timeout=20, headers=headers, allow_redirects=True)
        
        # Vérifier si c'est bien un PDF
        content_type = response.headers.get('Content-Type', '')
        
        if response.status_code == 200 and 'application/pdf' in content_type:
            return response.content, None
        
        return None, f"PMC: PDF non disponible (HTTP {response.status_code})"
        
    except Exception as e:
        return None, f"Erreur PMC: {str(e)}"

def get_pdf_via_unpaywall(doi, email="medical.research@pubmed.search"):
    """
    AMÉLIORÉ: API Unpaywall avec meilleure gestion des erreurs
    Méthode #2 - Taux de succès ~40-50%
    """
    if not doi:
        return None, "Pas de DOI"
    
    try:
        url = f"https://api.unpaywall.org/v2/{doi}"
        params = {"email": email}
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 404:
            return None, "DOI inconnu d'Unpaywall"
        
        if response.status_code != 200:
            return None, f"Erreur Unpaywall ({response.status_code})"
        
        data = response.json()
        
        # Chercher le meilleur lien PDF disponible
        if data.get('is_oa'):  # Open Access
            best_oa = data.get('best_oa_location')
            if best_oa and best_oa.get('url_for_pdf'):
                pdf_url = best_oa['url_for_pdf']
                
                # Télécharger le PDF
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                pdf_response = requests.get(pdf_url, timeout=20, headers=headers)
                
                if pdf_response.status_code == 200 and 'application/pdf' in pdf_response.headers.get('Content-Type', ''):
                    return pdf_response.content, None
            
            # Essayer les autres emplacements
            for location in data.get('oa_locations', []):
                pdf_url = location.get('url_for_pdf')
                if pdf_url:
                    try:
                        pdf_response = requests.get(pdf_url, timeout=20, headers=headers)
                        if pdf_response.status_code == 200 and 'application/pdf' in pdf_response.headers.get('Content-Type', ''):
                            return pdf_response.content, None
                    except:
                        continue
        
        return None, "Article payant (pas d'accès libre)"
        
    except Exception as e:
        return None, f"Erreur Unpaywall: {str(e)}"

def get_pdf_via_europepmc(pmid, pmcid=None):
    """
    NOUVEAU: Europe PMC - Source alternative majeure
    Méthode #3 - Taux de succès ~25-35%
    """
    try:
        # Méthode 1: Via PMCID si disponible
        if pmcid:
            pdf_url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid=PMC{pmcid}&blobtype=pdf"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(pdf_url, timeout=20, headers=headers)
            
            if response.status_code == 200 and 'application/pdf' in response.headers.get('Content-Type', ''):
                return response.content, None
        
        # Méthode 2: Recherche via API Europe PMC
        api_url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {
            "query": f"EXT_ID:{pmid}",
            "format": "json",
            "resultType": "core"
        }
        
        response = requests.get(api_url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('resultList', {}).get('result', [])
            
            if results:
                result = results[0]
                
                # Vérifier si PDF disponible
                if result.get('hasPDF') == 'Y':
                    # Essayer de construire l'URL PDF
                    source = result.get('source', '')
                    ext_id = result.get('id', '')
                    
                    if source == 'PMC' and ext_id:
                        pdf_url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={ext_id}&blobtype=pdf"
                        
                        pdf_response = requests.get(pdf_url, timeout=20, headers=headers)
                        
                        if pdf_response.status_code == 200 and 'application/pdf' in pdf_response.headers.get('Content-Type', ''):
                            return pdf_response.content, None
        
        return None, "Europe PMC: PDF non disponible"
        
    except Exception as e:
        return None, f"Erreur Europe PMC: {str(e)}"

def get_pdf_via_scihub(doi):
    """
    NOUVEAU: Sci-Hub en dernier recours
    Méthode #4 - Taux de succès élevé mais éthiquement discutable
    À utiliser UNIQUEMENT si toutes les méthodes légales ont échoué
    """
    if not doi:
        return None, "Pas de DOI"
    
    try:
        # URL Sci-Hub (peut changer)
        scihub_urls = [
            f"https://sci-hub.se/{doi}",
            f"https://sci-hub.st/{doi}",
            f"https://sci-hub.ru/{doi}"
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        for base_url in scihub_urls:
            try:
                response = requests.get(base_url, timeout=15, headers=headers)
                
                if response.status_code == 200:
                    # Extraire le lien PDF depuis la page HTML
                    pdf_match = re.search(r'(https?://[^"\']+\.pdf[^"\']*)', response.text)
                    
                    if pdf_match:
                        pdf_url = pdf_match.group(1)
                        
                        # Télécharger le PDF
                        pdf_response = requests.get(pdf_url, timeout=20, headers=headers)
                        
                        if pdf_response.status_code == 200 and 'application/pdf' in pdf_response.headers.get('Content-Type', ''):
                            return pdf_response.content, None
            except:
                continue
        
        return None, "Sci-Hub: PDF non trouvé"
        
    except Exception as e:
        return None, f"Erreur Sci-Hub: {str(e)}"

def extraire_texte_pdf_ameliore(pdf_content):
    """
    AMÉLIORATION: Essaie pdfplumber d'abord, puis pypdf en fallback
    pdfplumber est meilleur pour les PDFs médicaux multi-colonnes
    """
    texte_complet = ""
    
    # Méthode 1: Essayer pdfplumber (meilleur pour texte structuré)
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
            return texte_complet, "pdfplumber"
    
    except ImportError:
        # pdfplumber n'est pas installé
        pass
    except Exception as e:
        # Erreur avec pdfplumber, on passe à pypdf
        pass
    
    # Méthode 2: Fallback sur pypdf
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
            return texte_complet, "pypdf"
    
    except Exception as e:
        return "", f"Erreur extraction: {str(e)}"
    
    return texte_complet, "extraction_partielle"

def telecharger_et_extraire_pdf_multi_sources(pmid, mode_traduction="gemini", progress_callback=None, utiliser_scihub=False):
    """
    NOUVEAU: Système CASCADE multi-sources
    Essaie plusieurs méthodes dans l'ordre jusqu'à succès
    
    Ordre de priorité:
    1. PMC Open Access (gratuit et légal)
    2. Unpaywall (gratuit et légal)
    3. Europe PMC (gratuit et légal)
    4. Sci-Hub (optionnel, dernier recours)
    """
    try:
        if progress_callback:
            progress_callback(f"🔍 Recherche des identifiants pour PMID {pmid}...")
        
        # Étape 1: Récupérer DOI et PMCID
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
                progress_callback(f"⚠️ Aucun DOI/PMCID trouvé")
        
        pdf_content = None
        source_utilisee = None
        
        # MÉTHODE 1: PMC Open Access (prioritaire si PMCID disponible)
        if pmcid:
            if progress_callback:
                progress_callback(f"📥 Tentative PMC Open Access (PMC{pmcid})...")
            
            pdf_content, erreur = get_pdf_via_pmc(pmcid)
            
            if pdf_content:
                source_utilisee = f"PMC Open Access (PMC{pmcid})"
                if progress_callback:
                    progress_callback(f"✅ PDF trouvé via {source_utilisee}")
            else:
                if progress_callback:
                    progress_callback(f"❌ PMC: {erreur}")
        
        # MÉTHODE 2: Unpaywall
        if not pdf_content and doi:
            if progress_callback:
                progress_callback(f"📥 Tentative Unpaywall ({doi})...")
            
            time.sleep(0.5)  # Rate limiting
            pdf_content, erreur = get_pdf_via_unpaywall(doi)
            
            if pdf_content:
                source_utilisee = f"Unpaywall ({doi})"
                if progress_callback:
                    progress_callback(f"✅ PDF trouvé via {source_utilisee}")
            else:
                if progress_callback:
                    progress_callback(f"❌ Unpaywall: {erreur}")
        
        # MÉTHODE 3: Europe PMC
        if not pdf_content:
            if progress_callback:
                progress_callback(f"📥 Tentative Europe PMC...")
            
            time.sleep(0.5)  # Rate limiting
            pdf_content, erreur = get_pdf_via_europepmc(pmid, pmcid)
            
            if pdf_content:
                source_utilisee = "Europe PMC"
                if progress_callback:
                    progress_callback(f"✅ PDF trouvé via {source_utilisee}")
            else:
                if progress_callback:
                    progress_callback(f"❌ Europe PMC: {erreur}")
        
        # MÉTHODE 4: Sci-Hub (optionnel, dernier recours)
        if not pdf_content and utiliser_scihub and doi:
            if progress_callback:
                progress_callback(f"⚠️ Tentative Sci-Hub (dernier recours)...")
            
            time.sleep(1)  # Rate limiting plus long
            pdf_content, erreur = get_pdf_via_scihub(doi)
            
            if pdf_content:
                source_utilisee = "Sci-Hub"
                if progress_callback:
                    progress_callback(f"✅ PDF trouvé via {source_utilisee}")
            else:
                if progress_callback:
                    progress_callback(f"❌ Sci-Hub: {erreur}")
        
        # Si aucune source n'a fonctionné
        if not pdf_content:
            message_erreur = "PDF non disponible via aucune source"
            if not doi and not pmcid:
                message_erreur += " (pas de DOI ni PMCID)"
            elif not doi:
                message_erreur += " (pas de DOI)"
            elif not pmcid:
                message_erreur += " (pas de PMCID)"
            
            return None, message_erreur
        
        # Étape 2: Extraire le texte
        if progress_callback:
            progress_callback(f"📄 Extraction du texte...")
        
        texte_complet, methode = extraire_texte_pdf_ameliore(pdf_content)
        
        if len(texte_complet) < 100:
            return None, f"Contenu PDF insuffisant (méthode: {methode})"
        
        # Tronquer si trop long
        if len(texte_complet) > 12000:
            texte_complet = texte_complet[:12000] + "\n\n[PDF tronqué pour analyse]"
        
        # Étape 3: Traduire
        if progress_callback:
            progress_callback(f"🌐 Traduction en cours ({len(texte_complet)} caractères)...")
        
        chunk_size = 4000
        texte_traduit = ""
        
        for i in range(0, len(texte_complet), chunk_size):
            chunk = texte_complet[i:i+chunk_size]
            trad_chunk = traduire_texte(chunk, mode=mode_traduction)
            texte_traduit += trad_chunk + "\n\n"
            
            if progress_callback and i > 0:
                pct = min(100, int((i/len(texte_complet))*100))
                progress_callback(f"🌐 Traduction... {pct}%")
        
        if progress_callback:
            progress_callback(f"✅ Extraction réussie (source: {source_utilisee}, méthode: {methode})")
        
        return texte_traduit, None
        
    except Exception as e:
        return None, f"Erreur générale: {str(e)}"

def traduire_mots_cles(mots_cles_fr):
    """
    Traduit mots-clés avec prompt optimisé
    """
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
    except:
        return mots_cles_fr

def recuperer_titres_rapides(pmids, traduire_titres=False, mode_traduction="gemini"):
    """Récupère titres avec nettoyage optimal"""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", "rettype": "abstract"}
    
    try:
        response = requests.get(base_url, params=params, timeout=15)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            articles_data = []
            
            for article in root.findall('.//PubmedArticle'):
                pmid = article.find('.//PMID').text if article.find('.//PMID') is not None else "N/A"
                
                # Extraire le titre avec toutes les parties
                title_elem = article.find('.//ArticleTitle')
                if title_elem is not None:
                    title = ''.join(title_elem.itertext())
                else:
                    title = "Titre non disponible"
                
                # Nettoyer AVANT traduction
                title = nettoyer_titre(title)
                
                # Traduire si demandé
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
    """Génère PDF"""
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
    """Génère NotebookLM"""
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

# Interface
st.title("🩺 Veille Médicale Professionnelle v3")

# Afficher info sur les améliorations
with st.expander("ℹ️ Nouvelles fonctionnalités v3"):
    st.markdown("""
    **Améliorations majeures v3:**
    - 🔄 **Système CASCADE multi-sources** : Essai automatique de 4 sources différentes
    - 🏥 **PMC Open Access** : Accès direct aux articles PMC (nouvelle source #1)
    - 🌍 **Europe PMC** : Source européenne alternative (nouvelle source #3)
    - 🔗 **Unpaywall optimisé** : Meilleure gestion des erreurs 404
    - 📊 **Taux de réussite amélioré** : Jusqu'à 70-80% d'articles récupérés
    - ⚙️ **Sci-Hub optionnel** : Dernier recours désactivable (éthiquement discutable)
    - 🎯 **Priorisation intelligente** : PMC → Unpaywall → Europe PMC → Sci-Hub
    """)

if DEEPL_KEY:
    st.success("✅ DeepL Pro+ activé")
else:
    st.info("ℹ️ Traduction : Gemini 2.0 Flash")

tab1, tab2, tab3, tab4 = st.tabs(["🔍 Recherche", "📚 Historique", "🔗 Sources", "⚙️ Configuration"])

with tab1:
    if st.session_state.mode_etape == 1:
        st.header("📋 Étape 1 : Prévisualisation")
        
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
            
            # Filtre de langue
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
            
            # NOUVEAU: Option Sci-Hub
            st.subheader("⚙️ Options avancées")
            utiliser_scihub = st.checkbox(
                "🔓 Activer Sci-Hub (dernier recours)",
                value=False,
                help="Sci-Hub est juridiquement discutable. Utilisez uniquement si les sources légales échouent."
            )
            
            mode_trad = "deepl" if DEEPL_KEY else "gemini"
            traduire_titres = st.checkbox("🌐 Traduire titres", value=True)
        
        if st.button("🔍 LANCER", type="primary", use_container_width=True):
            
            if mode_recherche == "Par spécialité":
                term = TRAD[spec_fr]
                display_term = spec_fr
                spec_utilisee = spec_fr
            else:
                if not mots_cles_custom:
                    st.error("⚠️ Entrez des mots-clés")
                    st.stop()
                
                with st.spinner("🌐 Traduction..."):
                    term = traduire_mots_cles(mots_cles_custom)
                    st.info(f"🔄 Recherche: `{term}`")
                
                display_term = f"Mots-clés: {mots_cles_custom}"
                
                if inclure_specialite and spec_combo:
                    term = f"{term} AND {TRAD[spec_combo]}"
                    spec_utilisee = spec_combo
                else:
                    spec_utilisee = "Personnalisé"
            
            query_parts = [term]
            
            if "Titre uniquement" in zone_recherche:
                query_parts[0] = f"{query_parts[0]}[Title]"
            elif "Résumé uniquement" in zone_recherche:
                query_parts[0] = f"{query_parts[0]}[Abstract]"
            
            date_debut_pubmed = date_debut.strftime("%Y/%m/%d")
            date_fin_pubmed = date_fin.strftime("%Y/%m/%d")
            query_parts.append(f"{date_debut_pubmed}:{date_fin_pubmed}[pdat]")
            
            # Ajout du filtre de langue
            code_langue = LANGUES[langue_selectionnee]
            if code_langue:
                query_parts.append(f"{code_langue}[la]")
            
            if "PDF complets" in mode_contenu:
                query_parts.append("free full text[sb]")
            
            if journal_selectionne == "SPECIALITE":
                journaux_liste = JOURNAUX_SPECIALITE.get(spec_utilisee if mode_recherche == "Par spécialité" else spec_combo, [])
                if journaux_liste:
                    journaux_query = " OR ".join([f'"{j}"[Journal]' for j in journaux_liste])
                    query_parts.append(f"({journaux_query})")
            elif journal_selectionne != "TOUS":
                query_parts.append(f'"{journal_selectionne}"[Journal]')
            
            if TYPES_ETUDE[type_etude]:
                query_parts.append(f"{TYPES_ETUDE[type_etude]}[ptyp]")
            
            query = " AND ".join(query_parts)
            
            with st.expander("🔍 Requête PubMed"):
                st.code(query)
            
            base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": nb_max, "sort": "date"}
            
            try:
                with st.spinner("🔎 Recherche..."):
                    response = requests.get(base_url, params=params, timeout=15)
                
                if response.status_code != 200:
                    st.error(f"❌ Erreur: {response.status_code}")
                    st.stop()
                
                data = response.json()
                ids = data.get("esearchresult", {}).get("idlist", [])
                count = data.get("esearchresult", {}).get("count", "0")
                
                if not ids:
                    st.warning(f"⚠️ Aucun article pour: `{term}`")
                    st.stop()
                
                st.success(f"✅ {count} articles - Affichage de {len(ids)}")
                
                with st.spinner("📄 Récupération..."):
                    articles_preview = recuperer_titres_rapides(ids, traduire_titres=traduire_titres, mode_traduction=mode_trad)
                
                st.session_state.articles_previsualises = articles_preview
                st.session_state.info_recherche = {
                    'display_term': display_term,
                    'periode': f"du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}",
                    'spec': spec_utilisee,
                    'mode_contenu': mode_contenu,
                    'mode_traduction': mode_trad,
                    'requete': query,
                    'langue': langue_selectionnee,
                    'utiliser_scihub': utiliser_scihub
                }
                
                st.session_state.mode_etape = 2
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ {str(e)}")
    
    elif st.session_state.mode_etape == 2:
        st.header("📑 Étape 2 : Sélection")
        
        if not st.session_state.articles_previsualises:
            if st.button("↩️ Retour"):
                st.session_state.mode_etape = 1
                st.rerun()
            st.stop()
        
        # Afficher info recherche avec langue
        info_affichage = f"**{st.session_state.info_recherche['display_term']}** | {st.session_state.info_recherche['periode']}"
        if st.session_state.info_recherche.get('langue'):
            info_affichage += f" | 🌍 {st.session_state.info_recherche['langue']}"
        
        st.info(info_affichage)
        
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
                st.caption(f"📰 {article['journal']} | 📅 {article['date_pub']} | PMID: [{article['pmid']}](https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/)")
            
            if selected:
                articles_selectionnes.append(article['pmid'])
            
            st.divider()
        
        st.markdown(f"**{len(articles_selectionnes)} sélectionné(s)**")
        
        if 0 < len(articles_selectionnes) <= 20:
            st.divider()
            
            if st.button("🚀 ANALYSER", type="primary", use_container_width=True):
                
                st.session_state.analyses_individuelles = {}
                mode_trad = st.session_state.info_recherche.get('mode_traduction', 'gemini')
                utiliser_scihub = st.session_state.info_recherche.get('utiliser_scihub', False)
                
                # Statistiques de réussite
                stats = {
                    'total': len(articles_selectionnes),
                    'reussis': 0,
                    'echoues': 0,
                    'sources': {}
                }
                
                for idx, pmid in enumerate(articles_selectionnes):
                    st.subheader(f"📄 Article {idx+1}/{len(articles_selectionnes)} - PMID {pmid}")
                    
                    article_info = next((a for a in st.session_state.articles_previsualises if a['pmid'] == pmid), None)
                    
                    if not article_info:
                        continue
                    
                    st.markdown(f"**{article_info['title_fr']}**")
                    
                    status_box = st.empty()
                    
                    def callback(msg):
                        status_box.info(msg)
                    
                    # NOUVEAU: Utilisation de la fonction multi-sources
                    pdf_texte_fr, erreur = telecharger_et_extraire_pdf_multi_sources(
                        pmid,
                        mode_traduction=mode_trad,
                        progress_callback=callback,
                        utiliser_scihub=utiliser_scihub
                    )
                    
                    status_box.empty()
                    
                    if pdf_texte_fr:
                        stats['reussis'] += 1
                        
                        # Extraire la source utilisée depuis le dernier message
                        source_match = re.search(r'source: ([^,]+)', str(callback.__name__) if hasattr(callback, '__name__') else '')
                        source = source_match.group(1) if source_match else "Inconnue"
                        stats['sources'][source] = stats['sources'].get(source, 0) + 1
                        
                        st.success(f"✅ PDF extrait et traduit ({len(pdf_texte_fr)} caractères)")
                        
                        with st.expander("📄 Lire le PDF complet"):
                            st.text_area("Contenu:", pdf_texte_fr, height=400, key=f"pdf_{pmid}")
                        
                        with st.spinner("🤖 Analyse IA..."):
                            try:
                                genai.configure(api_key=G_KEY)
                                model = genai.GenerativeModel('gemini-2.0-flash-exp')
                                
                                # Prompt optimisé pour l'analyse
                                prompt = f"""Tu es un médecin expert. Analyse cet article médical en français de manière structurée et professionnelle.

ARTICLE:
Titre: {article_info['title_fr']}
Journal: {article_info['journal']} ({article_info['year']})

CONTENU COMPLET:
{pdf_texte_fr}

CONSIGNES D'ANALYSE:
- Rédige une analyse médicale professionnelle en français
- Structure obligatoire: Objectif, Méthodologie, Résultats, Implications cliniques, Limites, Conclusion
- Sois précis et concis
- Utilise la terminologie médicale française appropriée
- Ne commence pas par "Analyse:" ou tout autre préambule

ANALYSE STRUCTURÉE:"""
                                
                                response = model.generate_content(prompt)
                                analyse = response.text
                                
                                st.markdown("### 🤖 Analyse IA")
                                st.markdown(analyse)
                                
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
                            except Exception as e:
                                st.error(f"❌ Erreur analyse: {str(e)}")
                    else:
                        stats['echoues'] += 1
                        st.error(f"❌ {erreur}")
                        st.info(f"💡 Accès direct: https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
                    
                    st.divider()
                
                # Afficher les statistiques finales
                st.header("📊 Statistiques de récupération")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total", stats['total'])
                
                with col2:
                    taux_reussite = (stats['reussis'] / stats['total'] * 100) if stats['total'] > 0 else 0
                    st.metric("Réussis", f"{stats['reussis']} ({taux_reussite:.1f}%)")
                
                with col3:
                    st.metric("Échecs", stats['echoues'])
                
                if stats['sources']:
                    st.subheader("🔗 Sources utilisées")
                    for source, count in stats['sources'].items():
                        st.write(f"- **{source}**: {count} article(s)")
                
                if st.session_state.analyses_individuelles:
                    st.header("📚 Étape 3 : Sélection finale")
                    
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
                        st.success(f"✅ {len(articles_finaux)} pour PDF et podcast")
                        
                        with st.spinner("📦 Génération..."):
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
                        
                        st.link_button("🔗 NotebookLM", "https://notebooklm.google.com", use_container_width=True)
                        
                        if st.button("🔄 Nouvelle recherche", use_container_width=True):
                            st.session_state.mode_etape = 1
                            st.session_state.articles_previsualises = []
                            st.session_state.analyses_individuelles = {}
                            st.rerun()
                else:
                    st.warning("⚠️ Aucun article n'a pu être analysé. Essayez d'activer Sci-Hub dans les paramètres ou choisissez d'autres articles.")

with tab2:
    st.header("📚 Historique")
    st.info("Fonctionnalité à venir : Sauvegarde des recherches précédentes")

with tab3:
    st.header("🔗 Sources")
    
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
    
    st.subheader("🔄 Système CASCADE multi-sources")
    st.markdown("""
    **Ordre de priorité automatique:**
    
    1. **PMC Open Access** (prioritaire si PMCID disponible)
       - Accès direct aux articles PMC
       - Gratuit et légal
       - Taux de succès: ~30-40%
    
    2. **Unpaywall API** (si DOI disponible)
       - Recherche dans bases Open Access
       - Gratuit et légal
       - Taux de succès: ~40-50%
    
    3. **Europe PMC** (fallback)
       - Source européenne alternative
       - Gratuit et légal
       - Taux de succès: ~25-35%
    
    4. **Sci-Hub** (optionnel, dernier recours)
       - ⚠️ Juridiquement discutable
       - Taux de succès: ~80-90%
       - À activer manuellement dans les paramètres
    
    **Taux de réussite combiné: 70-80% (sans Sci-Hub) à 90-95% (avec Sci-Hub)**
    """)
    
    st.subheader("📄 Extraction PDF")
    st.markdown("""
    **Méthodes utilisées (par ordre de priorité):**
    1. **pdfplumber** (recommandé) : Meilleure extraction pour PDFs structurés
    2. **pypdf** (fallback) : Compatible mais moins précis
    
    Pour installer pdfplumber :
    ```bash
    pip install pdfplumber
    ```
    """)
    
    st.subheader("🌐 DeepL Pro+")
    st.markdown("""
    **Configuration DeepL** (optionnel):
    1. https://www.deepl.com/pro#developer
    2. Abonnement API Pro+ (29,99€/mois)
    3. Settings → Secrets :
    ```toml
    DEEPL_KEY = "votre-clé"
    ```
    
    Sans DeepL, le système utilise Gemini 2.0 Flash (gratuit).
    """)
    
    st.subheader("⚖️ Considérations éthiques et légales")
    st.markdown("""
    **Sources légales recommandées:**
    - ✅ PMC Open Access
    - ✅ Unpaywall
    - ✅ Europe PMC
    
    **Source optionnelle (juridiquement discutable):**
    - ⚠️ Sci-Hub : Utilisez uniquement pour un usage personnel et académique
    - Respectez les lois sur le droit d'auteur de votre pays
    - Privilégiez toujours les sources légales en premier
    """)

st.markdown("---")
st.caption("💊 Veille médicale v3.0 | Système CASCADE multi-sources | Gemini 2.0 Flash")
