import streamlit as st
import google.generativeai as genai
import requests
import json
from datetime import datetime, date, timedelta
import xml.etree.ElementTree as ET
from fpdf import FPDF
import io

st.set_page_config(page_title="Veille Médicale Pro", layout="wide")

# Récupération de la clé Gemini
try:
    G_KEY = st.secrets["GEMINI_KEY"]
except:
    st.error("⚠️ Clé GEMINI_KEY manquante dans les secrets")
    st.stop()

# Spécialités étendues
TRAD = {
    "Gynécologie": "Gynecology",
    "Endocrinologie": "Endocrinology",
    "Médecine Générale": "General Medicine",
    "Cardiologie": "Cardiology",
    "Neurologie": "Neurology",
    "Oncologie": "Oncology",
    "Pédiatrie": "Pediatrics",
    "Anesthésie-Réanimation": "Anesthesiology",
    "Obstétrique": "Obstetrics"
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
    "Gynécologie": ["BJOG", "Obstet Gynecol", "Am J Obstet Gynecol", "Hum Reprod", "Fertil Steril"],
    "Obstétrique": ["BJOG", "Obstet Gynecol", "Am J Obstet Gynecol", "Ultrasound Obstet Gynecol"],
    "Endocrinologie": ["J Clin Endocrinol Metab", "Diabetes Care", "Eur J Endocrinol", "Endocr Rev"],
    "Cardiologie": ["Circulation", "JACC", "Eur Heart J", "J Am Coll Cardiol", "Heart"],
    "Neurologie": ["Neurology", "Brain", "Lancet Neurol", "JAMA Neurol", "Ann Neurol"],
    "Oncologie": ["J Clin Oncol", "Lancet Oncol", "Cancer", "JAMA Oncol", "Ann Oncol"],
    "Pédiatrie": ["Pediatrics", "JAMA Pediatr", "Arch Dis Child", "J Pediatr"],
    "Anesthésie-Réanimation": ["Anesthesiology", "Br J Anaesth", "Anesth Analg", "Intensive Care Med"],
    "Médecine Générale": ["BMJ", "JAMA", "N Engl J Med", "Lancet", "Ann Intern Med"]
}

# Sources supplémentaires
SOURCES_SUPPLEMENTAIRES = {
    "HAS (Haute Autorité de Santé)": "https://www.has-sante.fr",
    "CNGOF (Collège National des Gynécologues et Obstétriciens Français)": "http://www.cngof.fr",
    "Vidal": "https://www.vidal.fr",
    "Cochrane Library": "https://www.cochranelibrary.com",
    "UpToDate": "https://www.uptodate.com"
}

# Initialiser l'historique
if 'historique' not in st.session_state:
    st.session_state.historique = []

# Fonction pour vérifier les mots-clés PubMed
def verifier_mots_cles_pubmed(mots_cles):
    """Vérifie si les mots-clés existent dans PubMed MeSH"""
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

# Fonction pour traduire les mots-clés
def traduire_mots_cles(mots_cles_fr, api_key):
    """Traduit les mots-clés français en anglais médical pour PubMed"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""Traduis ces mots-clés médicaux français en anglais médical précis pour une recherche PubMed.
Retourne UNIQUEMENT les termes anglais, sans explication.

Mots-clés français: {mots_cles_fr}

Termes anglais pour PubMed:"""
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        st.warning(f"⚠️ Traduction automatique échouée")
        return mots_cles_fr

# Fonction pour traduire un texte
def traduire_texte(texte, api_key):
    """Traduit un texte en français avec Gemini"""
    if not texte or texte == "Résumé non disponible":
        return texte
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""Traduis ce résumé médical en français de manière professionnelle et précise. 
Conserve tous les termes médicaux importants avec leur équivalent français entre parenthèses si nécessaire.

Texte à traduire:
{texte}

Traduction en français:"""
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        if "429" in str(e) or "quota" in str(e).lower():
            return f"[Quota API dépassé - Traduction non disponible]\n\n{texte}"
        return f"[Erreur de traduction]\n\n{texte}"

# Fonction PDF
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Veille Medicale - Synthese IA', 0, 1, 'C')
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
    
    def subsection_title(self, title):
        self.set_font('Arial', 'B', 11)
        self.cell(0, 8, title, 0, 1, 'L')
        self.ln(1)
    
    def body_text(self, text):
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 5, text)
        self.ln(2)

def generer_pdf_complet(spec, annee, nb_articles, pmids, synthese, articles_data):
    """Génère un PDF complet"""
    pdf = PDF()
    pdf.add_page()
    
    # PAGE DE GARDE
    pdf.set_font('Arial', 'B', 20)
    pdf.ln(30)
    pdf.cell(0, 15, 'VEILLE MEDICALE', 0, 1, 'C')
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'Synthese et Articles', 0, 1, 'C')
    pdf.ln(20)
    
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, f'Specialite: {spec}', 0, 1, 'C')
    pdf.cell(0, 8, f'Periode: {annee}', 0, 1, 'C')
    pdf.cell(0, 8, f'Nombre d\'articles: {nb_articles}', 0, 1, 'C')
    pdf.cell(0, 8, f'Date: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'C')
    
    # SYNTHÈSE IA
    pdf.add_page()
    pdf.section_title('PARTIE 1 : SYNTHESE PAR INTELLIGENCE ARTIFICIELLE')
    
    try:
        synthese_clean = synthese.encode('latin-1', 'ignore').decode('latin-1')
    except:
        synthese_clean = synthese.encode('ascii', 'ignore').decode('ascii')
    
    pdf.body_text(synthese_clean)
    
    # ARTICLES DÉTAILLÉS
    pdf.add_page()
    pdf.section_title('PARTIE 2 : ARTICLES ETUDIES')
    pdf.ln(5)
    
    for i, article in enumerate(articles_data, 1):
        pdf.subsection_title(f'Article {i}')
        
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 6, f'PMID: {article["pmid"]}', 0, 1)
        
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 6, 'Titre:', 0, 1)
        try:
            title_clean = article['title'].encode('latin-1', 'ignore').decode('latin-1')
        except:
            title_clean = article['title'].encode('ascii', 'ignore').decode('ascii')
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 5, title_clean)
        pdf.ln(2)
        
        if article['authors']:
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(0, 6, 'Auteurs:', 0, 1)
            pdf.set_font('Arial', '', 10)
            authors_text = ', '.join(article['authors'])
            try:
                authors_clean = authors_text.encode('latin-1', 'ignore').decode('latin-1')
            except:
                authors_clean = authors_text.encode('ascii', 'ignore').decode('ascii')
            pdf.multi_cell(0, 5, authors_clean)
            pdf.ln(2)
        
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 6, 'Publication:', 0, 1)
        pdf.set_font('Arial', '', 10)
        try:
            journal_clean = article['journal'].encode('latin-1', 'ignore').decode('latin-1')
        except:
            journal_clean = article['journal'].encode('ascii', 'ignore').decode('ascii')
        pdf.cell(0, 5, f'{journal_clean} ({article["year"]})', 0, 1)
        pdf.ln(2)
        
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 6, 'Resume (Francais):', 0, 1)
        pdf.set_font('Arial', '', 9)
        try:
            abstract_clean = article['abstract_fr'].encode('latin-1', 'ignore').decode('latin-1')
        except:
            abstract_clean = article['abstract_fr'].encode('ascii', 'ignore').decode('ascii')
        pdf.multi_cell(0, 4, abstract_clean)
        pdf.ln(3)
        
        pdf.set_font('Arial', 'I', 9)
        pdf.cell(0, 5, f'Lien: https://pubmed.ncbi.nlm.nih.gov/{article["pmid"]}/', 0, 1)
        
        pdf.ln(5)
        pdf.set_draw_color(180, 180, 180)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        if i % 2 == 0 and i < len(articles_data):
            pdf.add_page()
    
    pdf_output = io.BytesIO()
    pdf_string = pdf.output(dest='S').encode('latin-1')
    pdf_output.write(pdf_string)
    pdf_output.seek(0)
    
    return pdf_output.getvalue()

def recuperer_abstracts(pmids, traduire=False, api_key=None):
    """Récupère les résumés complets depuis PubMed"""
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
        st.warning(f"Erreur lors de la récupération: {str(e)}")
        return []
    
    return []

def sauvegarder_recherche(spec, annee, type_etude, langue, pmids, synthese, mots_cles=""):
    """Sauvegarde la recherche"""
    recherche = {
        'date': datetime.now().strftime("%d/%m/%Y %H:%M"),
        'specialite': spec,
        'annee': annee,
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

tab1, tab2, tab3 = st.tabs(["🔍 Nouvelle Recherche", "📚 Historique", "🔗 Sources Complémentaires"])

with tab1:
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Mode de recherche
        mode_recherche = st.radio("Mode de recherche", ["Par spécialité", "Par mots-clés"], horizontal=True)
        
        if mode_recherche == "Par spécialité":
            spec_fr = st.selectbox("🏥 Spécialité médicale", list(TRAD.keys()))
            mots_cles_custom = ""
            mots_cles_originaux = ""
            
            # Journal spécifique
            st.subheader("📰 Journal spécifique (optionnel)")
            journaux_dispo = ["Tous"] + JOURNAUX_SPECIALITE.get(spec_fr, [])
            journal_selectionne = st.selectbox("Journal", journaux_dispo)
            
        else:
            spec_fr = None
            journal_selectionne = "Tous"
            
            # Option combinée spécialité + mots-clés
            inclure_specialite = st.checkbox("🔬 Inclure une spécialité", value=False)
            if inclure_specialite:
                spec_combo = st.selectbox("Spécialité", list(TRAD.keys()))
            else:
                spec_combo = None
            
            mots_cles_custom = st.text_area(
                "🔎 Mots-clés de recherche",
                placeholder="Ex: diabète gestationnel\ncancer du sein triple négatif\nhypertension résistante",
                help="Un mot-clé par ligne ou séparés par des virgules",
                height=100
            )
            mots_cles_originaux = mots_cles_custom
            
            # Vérification des mots-clés PubMed
            if mots_cles_custom:
                if st.button("🔍 Vérifier dans PubMed"):
                    with st.spinner("Vérification..."):
                        mots_cles_en = traduire_mots_cles(mots_cles_custom, G_KEY)
                        existe, count = verifier_mots_cles_pubmed(mots_cles_en)
                        
                        if existe:
                            st.success(f"✅ {count:,} articles trouvés avec ces mots-clés")
                            st.info(f"Traduction: {mots_cles_en}")
                        elif existe is False:
                            st.warning("⚠️ Aucun article trouvé. Essayez d'autres termes.")
                        else:
                            st.error("❌ Erreur de vérification")
        
        # Recherche dans titre ou résumé
        st.subheader("🎯 Zone de recherche")
        zone_recherche = st.radio(
            "Chercher les mots-clés dans:",
            ["Titre et résumé", "Titre uniquement", "Résumé uniquement"],
            horizontal=False
        )
        
        # Calendrier de dates
        st.subheader("📅 Période")
        col1, col2 = st.columns(2)
        
        with col1:
            date_debut = st.date_input(
                "Date de début",
                value=date(2024, 1, 1),
                min_value=date(2000, 1, 1),
                max_value=date.today()
            )
        
        with col2:
            date_fin = st.date_input(
                "Date de fin",
                value=date.today(),
                min_value=date_debut,
                max_value=date.today()
            )
        
        # Accès libre
        st.subheader("🔓 Accès aux articles")
        acces_libre = st.checkbox("📖 Uniquement articles en accès libre complet (PDF gratuit)", value=False)
        
        st.subheader("🔬 Filtres avancés")
        type_etude = st.selectbox("Type d'étude", list(TYPES_ETUDE.keys()))
        
        langue = st.selectbox("Langue", [
            "Toutes",
            "Anglais",
            "Français",
            "Espagnol",
            "Allemand"
        ])
        
        traduire_abstracts = st.checkbox("🌐 Traduire les résumés en français", value=True)
        
        nb = st.slider("📊 Nombre d'articles", 1, 20, 5)
        
        st.divider()
        st.caption("🔬 PubMed/NCBI")
        st.caption("🤖 Gemini 2.5")

    if st.button("🔍 Lancer la recherche", type="primary", use_container_width=True):
        
        if mode_recherche == "Par mots-clés" and not mots_cles_custom:
            st.error("⚠️ Veuillez entrer des mots-clés")
            st.stop()
        
        # Construction de la requête
        if mode_recherche == "Par spécialité":
            term = TRAD[spec_fr]
            display_term = spec_fr
            mots_cles_traduits = None
        else:
            with st.spinner("🌐 Traduction des mots-clés..."):
                mots_cles_traduits = traduire_mots_cles(mots_cles_custom, G_KEY)
            
            term = mots_cles_traduits
            
            # Ajouter spécialité si demandé
            if inclure_specialite and spec_combo:
                term = f"{term} AND {TRAD[spec_combo]}"
            
            display_term = f"Mots-clés: {mots_cles_custom}"
            st.info(f"🔄 Traduction: {mots_cles_traduits}")
        
        # Construction de la requête complète
        query_parts = [term]
        
        # Filtre de zone de recherche
        if zone_recherche == "Titre uniquement":
            query_parts[0] = f"{query_parts[0]}[Title]"
        elif zone_recherche == "Résumé uniquement":
            query_parts[0] = f"{query_parts[0]}[Abstract]"
        
        # Filtre de dates
        date_debut_str = date_debut.strftime("%Y/%m/%d")
        date_fin_str = date_fin.strftime("%Y/%m/%d")
        query_parts.append(f"{date_debut_str}:{date_fin_str}[pdat]")
        
        # Accès libre
        if acces_libre:
            query_parts.append("free full text[sb]")
        
        # Journal spécifique
        if journal_selectionne != "Tous":
            query_parts.append(f'"{journal_selectionne}"[Journal]')
        
        # Type d'étude
        if TYPES_ETUDE[type_etude]:
            query_parts.append(f"{TYPES_ETUDE[type_etude]}[ptyp]")
        
        # Langue
        langue_codes = {
            "Anglais": "eng",
            "Français": "fre",
            "Espagnol": "spa",
            "Allemand": "ger"
        }
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
        
        with st.expander("🔍 Détails de la requête"):
            st.write(f"**Recherche:** {display_term}")
            st.write(f"**Période:** {date_debut_str} à {date_fin_str}")
            st.write(f"**Zone:** {zone_recherche}")
            if acces_libre:
                st.write("**Accès:** Articles gratuits uniquement")
            if journal_selectionne != "Tous":
                st.write(f"**Journal:** {journal_selectionne}")
            st.code(query)
        
        try:
            with st.spinner("🔎 Recherche sur PubMed..."):
                response = requests.get(
                    base_url,
                    params=params,
                    headers={'User-Agent': 'Streamlit Medical App'},
                    timeout=15
                )
            
            if response.status_code != 200:
                st.error(f"❌ Erreur PubMed: {response.status_code}")
                st.stop()
            
            data = response.json()
            search_result = data.get("esearchresult", {})
            ids = search_result.get("idlist", [])
            count = search_result.get("count", "0")
            
            if not ids:
                st.warning("⚠️ Aucun article trouvé")
                st.info("💡 Essayez d'élargir les critères")
                st.stop()
            
            st.success(f"✅ {count} articles trouvés - Affichage de {len(ids)}")
            
            message_trad = "📄 Récupération et traduction..." if traduire_abstracts else "📄 Récupération..."
            with st.spinner(message_trad):
                articles_complets = recuperer_abstracts(ids, traduire=traduire_abstracts, api_key=G_KEY)
            
            if articles_complets:
                st.subheader("📚 Articles avec résumés")
                
                for i, article in enumerate(articles_complets, 1):
                    with st.expander(f"**Article {i}** - {article['title'][:100]}..."):
                        st.markdown(f"**PMID:** [{article['pmid']}](https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/)")
                        st.markdown(f"**Journal:** {article['journal']} ({article['year']})")
                        if article['authors']:
                            st.markdown(f"**Auteurs:** {', '.join(article['authors'][:3])}")
                        
                        if traduire_abstracts:
                            st.markdown("**📖 Résumé (Français):**")
                            st.write(article['abstract_fr'])
                            
                            with st.expander("🔤 Original"):
                                st.write(article['abstract'])
                        else:
                            st.markdown("**📖 Résumé:**")
                            st.write(article['abstract'])
            
            st.divider()
            
            st.subheader("🤖 Synthèse par IA")
            
            with st.spinner("⏳ Analyse..."):
                try:
                    genai.configure(api_key=G_KEY)
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    contexte = ""
                    if articles_complets:
                        for art in articles_complets:
                            resume = art['abstract_fr'] if traduire_abstracts else art['abstract']
                            contexte += f"\n\nPMID {art['pmid']}:\nTitre: {art['title']}\nRésumé: {resume}\n"
                    
                    liens = "\n".join([f"- https://pubmed.ncbi.nlm.nih.gov/{pmid}/" for pmid in ids])
                    
                    spec_texte = spec_fr if mode_recherche == "Par spécialité" else f"Mots-clés: {mots_cles_custom}"
                    
                    prompt = f"""Tu es un médecin expert en veille scientifique.

Analyse {len(ids)} articles de PubMed.

**Critères:**
- {spec_texte}
- Période: {date_debut_str} à {date_fin_str}
- Type: {type_etude}

**Articles:**
{contexte}

**PMIDs:** {', '.join(ids)}

Rédige une synthèse en français:

## 📊 Vue d'ensemble
## 🔬 Tendances principales
## 💡 Découvertes notables
## 🏥 Implications cliniques
## ⚠️ Limites et perspectives

## 🔗 Sources
{liens}

Cite les PMIDs."""
                    
                    response_ia = model.generate_content(prompt)
                    synthese = response_ia.text
                    
                    st.markdown(synthese)
                    
                    # Info NotebookLM
                    st.info("💡 **Astuce:** Copiez le contenu du PDF dans NotebookLM (notebooklm.google.com) pour générer un podcast audio de cette synthèse !")
                    
                    sauvegarder_recherche(
                        spec_fr if mode_recherche == "Par spécialité" else "Personnalisé",
                        f"{date_debut_str} à {date_fin_str}",
                        type_etude,
                        langue,
                        ids,
                        synthese,
                        mots_cles_originaux
                    )
                    
                    st.success("✅ Synthèse sauvegardée !")
                    
                    col1, col2 = st.columns(2)
                    
                    nom_fichier = spec_fr if mode_recherche == "Par spécialité" else "recherche"
                    
                    with col1:
                        st.download_button(
                            label="📥 TXT",
                            data=synthese,
                            file_name=f"synthese_{nom_fichier}.txt",
                            mime="text/plain"
                        )
                    
                    with col2:
                        with st.spinner("📄 Génération PDF..."):
                            pdf_bytes = generer_pdf_complet(
                                display_term,
                                f"{date_debut_str} à {date_fin_str}",
                                len(ids),
                                ids,
                                synthese,
                                articles_complets
                            )
                        st.download_button(
                            label="📄 PDF Complet",
                            data=pdf_bytes,
                            file_name=f"veille_{nom_fichier}.pdf",
                            mime="application/pdf"
                        )
                    
                except Exception as e:
                    st.error(f"❌ Erreur IA: {str(e)}")
        
        except Exception as e:
            st.error(f"❌ Erreur: {str(e)}")

with tab2:
    st.header("📚 Historique")
    
    if not st.session_state.historique:
        st.info("Aucune recherche enregistrée")
    else:
        for i, rech in enumerate(st.session_state.historique):
            titre = f"🔍 {rech['date']} - {rech['specialite']} - {rech['nb_articles']} articles"
            
            with st.expander(titre):
                st.markdown(f"**Spécialité:** {rech['specialite']}")
                if rech.get('mots_cles'):
                    st.markdown(f"**Mots-clés:** {rech['mots_cles']}")
                st.markdown(f"**Période:** {rech['annee']}")
                st.markdown(f"**PMIDs:** {', '.join(rech['pmids'])}")
                
                st.divider()
                st.markdown(rech['synthese'])

with tab3:
    st.header("🔗 Sources Médicales Complémentaires")
    
    st.markdown("""
    ### Sources françaises officielles
    """)
    
    for nom, url in SOURCES_SUPPLEMENTAIRES.items():
        st.markdown(f"**{nom}**")
        st.markdown(f"[Accéder au site]({url})")
        st.divider()
    
    st.info("💡 Ces sources complètent PubMed avec des recommandations françaises et des bases de données spécialisées.")

st.markdown("---")
st.caption("💊 Veille médicale professionnelle | PubMed + Gemini 2.5")
