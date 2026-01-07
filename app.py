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

# SOURCES PAR SPÉCIALITÉ
SOURCES_PAR_SPECIALITE = {
    "Gynécologie": {
        "CNGOF": {
            "url": "http://www.cngof.fr",
            "description": "Recommandations françaises",
            "recherche": "http://www.cngof.fr/?s="
        }
    },
    "Obstétrique": {
        "CNGOF": {
            "url": "http://www.cngof.fr",
            "description": "Recommandations françaises",
            "recherche": "http://www.cngof.fr/?s="
        }
    },
    "Anesthésie-Réanimation": {
        "SFAR": {
            "url": "https://sfar.org",
            "description": "SFAR",
            "recherche": "https://sfar.org/?s="
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
if 'articles_previsualises' not in st.session_state:
    st.session_state.articles_previsualises = []
if 'mode_etape' not in st.session_state:
    st.session_state.mode_etape = 1
if 'info_recherche' not in st.session_state:
    st.session_state.info_recherche = {}
if 'analyses_individuelles' not in st.session_state:
    st.session_state.analyses_individuelles = {}

def get_pdf_link(pmid):
    """Récupère le lien PDF PMC"""
    try:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
        params = {"dbfrom": "pubmed", "db": "pmc", "id": pmid, "retmode": "xml"}
        response = requests.get(base_url, params=params, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            pmc_id = root.find('.//Link/Id')
            if pmc_id is not None:
                return f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id.text}/pdf/", pmc_id.text
        return None, None
    except:
        return None, None

def telecharger_et_extraire_pdf(pmid, traduire=False, api_key=None, progress_callback=None):
    """Télécharge, extrait et traduit le PDF"""
    try:
        pdf_url, pmc_id = get_pdf_link(pmid)
        if not pdf_url:
            return None, "PDF non disponible"
        
        if progress_callback:
            progress_callback(f"📥 Téléchargement PDF PMID {pmid}...")
        
        response = requests.get(pdf_url, timeout=30)
        if response.status_code != 200:
            return None, f"Erreur: {response.status_code}"
        
        if progress_callback:
            progress_callback(f"📄 Extraction texte PMID {pmid}...")
        
        try:
            pdf_file = BytesIO(response.content)
            pdf_reader = pypdf.PdfReader(pdf_file)
            
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
                    progress_callback(f"🌐 Traduction PMID {pmid}...")
                
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    # Traduction en un seul bloc pour cohérence
                    prompt_trad = f"""Traduis cet article médical en français professionnel.
Conserve la structure et les termes techniques.

{texte_complet[:8000]}

Traduction:"""
                    
                    response_trad = model.generate_content(prompt_trad)
                    return response_trad.text, None
                except:
                    return texte_complet + "\n\n[Traduction échouée]", None
            
            return texte_complet, None
        except Exception as e:
            return None, f"Erreur extraction: {str(e)}"
    except Exception as e:
        return None, f"Erreur: {str(e)}"

def traduire_titre(titre, api_key):
    """Traduit un titre en français (UNE SEULE traduction)"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""Traduis ce titre médical en français. Donne UNE SEULE traduction, la plus naturelle et précise.

Titre: {titre}

Traduction:"""
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return titre

def traduire_mots_cles(mots_cles_fr, api_key):
    """Traduit mots-clés"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""Traduis en anglais médical:

{mots_cles_fr}

Anglais:"""
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return mots_cles_fr

def recuperer_titres_rapides(pmids, traduire_titres=False, api_key=None):
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
                
                # UNE SEULE traduction
                title_fr = traduire_titre(title, api_key) if traduire_titres and title != "Titre non disponible" and api_key else title
                
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
    """Génère PDF avec articles sélectionnés uniquement"""
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
    """Génère fichier NotebookLM pour articles sélectionnés"""
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
st.markdown("*Recherche en 2 étapes avec traduction médicale professionnelle*")

tab1, tab2, tab3 = st.tabs(["🔍 Recherche", "📚 Historique", "💡 Traducteurs Pro"])

with tab1:
    # ÉTAPE 1 : PRÉVISUALISATION
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
                jour_debut = st.selectbox("J", range(1, 32), index=0, key="j1")
                mois_debut = st.selectbox("M", range(1, 13), index=0, key="m1", format_func=lambda x: MOIS_FR[x])
                annee_debut = st.selectbox("A", range(2000, 2027), index=24, key="a1")
            
            with col2:
                jour_fin = st.selectbox("J", range(1, 32), index=date.today().day-1, key="j2")
                mois_fin = st.selectbox("M", range(1, 13), index=date.today().month-1, key="m2", format_func=lambda x: MOIS_FR[x])
                annee_fin = st.selectbox("A", range(2000, 2027), index=26, key="a2")
            
            try:
                date_debut = date(annee_debut, mois_debut, jour_debut)
                date_fin = date(annee_fin, mois_fin, jour_fin)
            except:
                date_debut = date(2024, 1, 1)
                date_fin = date.today()
            
            st.subheader("🔬 Filtres")
            
            mode_contenu = st.radio(
                "Type:",
                ["PDF complets uniquement", "Titre + résumé", "Titre uniquement"]
            )
            
            type_etude = st.selectbox("Étude", list(TYPES_ETUDE.keys()))
            nb_max = st.slider("Max résultats", 10, 200, 50, 10)
            traduire_titres = st.checkbox("🌐 Traduire titres", value=True)
        
        if st.button("🔍 LANCER", type="primary", use_container_width=True):
            
            if mode_recherche == "Par spécialité":
                term = TRAD[spec_fr]
                display_term = spec_fr
            else:
                if not mots_cles_custom:
                    st.error("⚠️ Entrez des mots-clés")
                    st.stop()
                term = traduire_mots_cles(mots_cles_custom, G_KEY)
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
                with st.spinner("Recherche..."):
                    response = requests.get(base_url, params=params, timeout=15)
                
                if response.status_code != 200:
                    st.error(f"❌ Erreur: {response.status_code}")
                    st.stop()
                
                data = response.json()
                ids = data.get("esearchresult", {}).get("idlist", [])
                count = data.get("esearchresult", {}).get("count", "0")
                
                if not ids:
                    st.warning("⚠️ Aucun article")
                    st.stop()
                
                st.success(f"✅ {count} articles - Affichage de {len(ids)}")
                
                with st.spinner("Récupération..."):
                    articles_preview = recuperer_titres_rapides(ids, traduire_titres=traduire_titres, api_key=G_KEY)
                
                st.session_state.articles_previsualises = articles_preview
                st.session_state.info_recherche = {
                    'display_term': display_term,
                    'periode': f"du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}",
                    'spec': spec_fr if mode_recherche == "Par spécialité" else "Personnalisé",
                    'mode_contenu': mode_contenu
                }
                
                st.session_state.mode_etape = 2
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ {str(e)}")
    
    # ÉTAPE 2 : SÉLECTION ET ANALYSE
    elif st.session_state.mode_etape == 2:
        st.header("📑 Étape 2 : Sélection et Analyse")
        
        if not st.session_state.articles_previsualises:
            st.warning("Aucun article")
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
            
            if st.button("🚀 ANALYSER LES ARTICLES", type="primary", use_container_width=True):
                
                st.session_state.analyses_individuelles = {}
                
                # ANALYSE ARTICLE PAR ARTICLE
                for idx, pmid in enumerate(articles_selectionnes):
                    st.subheader(f"📄 Article {idx+1}/{len(articles_selectionnes)} - PMID {pmid}")
                    
                    # Trouver l'article
                    article_info = next((a for a in st.session_state.articles_previsualises if a['pmid'] == pmid), None)
                    
                    if not article_info:
                        continue
                    
                    st.markdown(f"**{article_info['title_fr']}**")
                    
                    # Extraction et traduction PDF
                    with st.spinner(f"Extraction et traduction du PDF {idx+1}..."):
                        
                        status = st.empty()
                        
                        def callback(msg):
                            status.text(msg)
                        
                        pdf_texte_fr, erreur = telecharger_et_extraire_pdf(
                            pmid,
                            traduire=True,
                            api_key=G_KEY,
                            progress_callback=callback
                        )
                        
                        status.empty()
                        
                        if pdf_texte_fr:
                            st.success(f"✅ PDF extrait et traduit ({len(pdf_texte_fr)} caractères)")
                            
                            # AFFICHER LE PDF TRADUIT
                            with st.expander("📄 Lire le PDF complet traduit"):
                                st.text_area(
                                    "Contenu:",
                                    pdf_texte_fr,
                                    height=400,
                                    key=f"pdf_display_{pmid}"
                                )
                            
                            # ANALYSE IA INDIVIDUELLE
                            with st.spinner("Analyse IA..."):
                                genai.configure(api_key=G_KEY)
                                model = genai.GenerativeModel('gemini-2.5-flash')
                                
                                prompt_analyse = f"""Analyse médicale approfondie.

Titre: {article_info['title_fr']}
Journal: {article_info['journal']}
Année: {article_info['year']}

Contenu complet:
{pdf_texte_fr}

Analyse en français:

## Objectif
## Méthodologie
## Résultats principaux
## Implications cliniques
## Limites
## Conclusion

Sois précis et détaillé."""
                                
                                response_analyse = model.generate_content(prompt_analyse)
                                analyse_ia = response_analyse.text
                            
                            st.markdown("### 🤖 Analyse IA")
                            st.markdown(analyse_ia)
                            
                            # SAUVEGARDER
                            st.session_state.analyses_individuelles[pmid] = {
                                'pmid': pmid,
                                'title': article_info['title'],
                                'title_fr': article_info['title_fr'],
                                'journal': article_info['journal'],
                                'year': article_info['year'],
                                'date_pub': article_info['date_pub'],
                                'pdf_texte_fr': pdf_texte_fr,
                                'analyse_ia': analyse_ia
                            }
                            
                        else:
                            st.error(f"❌ {erreur}")
                    
                    st.divider()
                
                # ÉTAPE 3: SÉLECTION FINALE
                st.header("📚 Étape 3 : Sélection pour PDF final et Podcast")
                
                st.info("Sélectionnez les articles à inclure dans le PDF final et le podcast NotebookLM")
                
                articles_finaux = []
                
                for pmid, data in st.session_state.analyses_individuelles.items():
                    col_check_final, col_info_final = st.columns([0.1, 0.9])
                    
                    with col_check_final:
                        include_final = st.checkbox("", key=f"final_{pmid}", value=True, label_visibility="collapsed")
                    
                    with col_info_final:
                        st.markdown(f"**{data['title_fr']}**")
                        st.caption(f"{data['journal']} | {data['date_pub']}")
                    
                    if include_final:
                        articles_finaux.append(data)
                    
                    st.divider()
                
                if articles_finaux:
                    st.success(f"✅ {len(articles_finaux)} article(s) sélectionné(s) pour le PDF et podcast")
                    
                    # GÉNÉRER PDF ET NOTEBOOKLM
                    pdf_final = generer_pdf_selectionne(
                        st.session_state.info_recherche['spec'],
                        st.session_state.info_recherche['periode'],
                        articles_finaux
                    )
                    
                    notebooklm_final = generer_notebooklm_selectionne(articles_finaux)
                    
                    st.divider()
                    st.subheader("📥 Téléchargements")
                    
                    col_dl1, col_dl2 = st.columns(2)
                    
                    with col_dl1:
                        st.download_button(
                            "📄 PDF Final",
                            pdf_final,
                            f"veille_complete_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf"
                        )
                    
                    with col_dl2:
                        st.download_button(
                            "🎙️ NotebookLM",
                            notebooklm_final,
                            f"podcast_{datetime.now().strftime('%Y%m%d')}.txt"
                        )
                    
                    if st.button("🔄 Nouvelle recherche"):
                        st.session_state.mode_etape = 1
                        st.session_state.articles_previsualises = []
                        st.session_state.analyses_individuelles = {}
                        st.rerun()

with tab2:
    st.header("📚 Historique")
    st.info("Historique des recherches")

with tab3:
    st.header("💡 Traducteurs Médicaux Professionnels")
    
    st.markdown("""
## 🌐 Traducteurs Recommandés

### 1. **DeepL Pro** (⭐⭐⭐⭐⭐)
**Prix:** 8,74€/mois (API) ou 30€/mois (Pro+)
**Qualités:**
- ✅ Meilleure traduction médicale actuelle
- ✅ Contexte médical bien compris
- ✅ Termes techniques préservés
- ✅ API disponible
**Site:** https://www.deepl.com/pro-api

### 2. **ModernMT Medical** (⭐⭐⭐⭐)
**Prix:** Sur devis
**Qualités:**
- ✅ Spécialisé domaine médical
- ✅ Apprentissage adaptatif
- ✅ Terminologie médicale
**Site:** https://www.modernmt.com

### 3. **Microsoft Translator Custom** (⭐⭐⭐⭐)
**Prix:** Pay-as-you-go (~10€/million caractères)
**Qualités:**
- ✅ Personnalisable
- ✅ Bon pour termes techniques
- ✅ API Azure
**Site:** https://azure.microsoft.com/translator

### 4. **Gemini 2.5 Flash** (⭐⭐⭐⭐ - Actuel)
**Prix:** Gratuit jusqu'à 1500 req/jour
**Qualités:**
- ✅ Très bon pour médical
- ✅ Gratuit jusqu'à quota
- ✅ Déjà intégré
**Note:** C'est ce que vous utilisez actuellement !

---

## 💰 Recommandation Budget

**Pour usage régulier:**
- **DeepL Pro** (8,74€/mois) : Meilleur rapport qualité/prix
- **Gemini** (gratuit) : Excellent et déjà intégré

**Pour usage intensif:**
- **DeepL API** + **Gemini** en backup
    """)

st.markdown("---")
st.caption("💊 Veille médicale | PubMed + Gemini 2.5")
