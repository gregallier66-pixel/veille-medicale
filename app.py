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

# Fonction pour parser une date au format dd/mm/yyyy
def parse_date_fr(date_str):
    """Convertit une date dd/mm/yyyy en objet date"""
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").date()
    except:
        return None

# Fonction pour formater une date en dd/mm/yyyy
def format_date_fr(date_obj):
    """Convertit un objet date en dd/mm/yyyy"""
    return date_obj.strftime("%d/%m/%Y")

# Fonction pour récupérer le lien PDF
def get_pdf_link(pmid):
    """Récupère le lien du PDF en libre accès"""
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

# Fonction pour vérifier les mots-clés
def verifier_mots_cles_pubmed(mots_cles):
    """Vérifie si les mots-clés existent dans PubMed"""
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
    """Traduit les mots-clés français en anglais"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""Traduis ces mots-clés médicaux français en anglais médical pour PubMed.
Retourne UNIQUEMENT les termes anglais.

Mots-clés français: {mots_cles_fr}

Termes anglais:"""
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return mots_cles_fr

# Fonction pour traduire un texte
def traduire_texte(texte, api_key):
    """Traduit un texte en français"""
    if not texte or texte == "Résumé non disponible":
        return texte
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""Traduis ce texte médical en français de manière professionnelle.

Texte:
{texte}

Traduction:"""
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        if "429" in str(e) or "quota" in str(e).lower():
            return f"[Quota dépassé]\n\n{texte}"
        return f"[Erreur]\n\n{texte}"

# Fonction PDF
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
    """Génère un PDF complet"""
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
    """Récupère les résumés depuis PubMed"""
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
    """Génère un fichier pour NotebookLM"""
    contenu = f"""# VEILLE MÉDICALE - SYNTHÈSE POUR PODCAST
Date: {datetime.now().strftime("%d/%m/%Y")}

## SYNTHÈSE PRINCIPALE

{synthese}

## ARTICLES SOURCES

"""
    
    for i, article in enumerate(articles_data, 1):
        contenu += f"""
### Article {i}
**Titre:** {article['title']}
**Auteurs:** {', '.join(article['authors'][:5])}
**Journal:** {article['journal']} ({article['year']})
**PMID:** {article['pmid']}

**Résumé:**
{article['abstract_fr']}

---
"""
    
    return contenu

def sauvegarder_recherche(spec, periode, type_etude, langue, pmids, synthese, mots_cles=""):
    """Sauvegarde la recherche"""
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

tab1, tab2, tab3 = st.tabs(["🔍 Recherche", "📚 Historique", "🔗 Sources"])

with tab1:
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        mode_recherche = st.radio("Mode", ["Par spécialité", "Par mots-clés"], horizontal=True)
        
        if mode_recherche == "Par spécialité":
            spec_fr = st.selectbox("🏥 Spécialité", list(TRAD.keys()))
            mots_cles_custom = ""
            mots_cles_originaux = ""
            
            st.subheader("📰 Journal (optionnel)")
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
        
        st.subheader("📅 Période")
        
        col1, col2 = st.columns(2)
        
        with col1:
            date_debut_input = st.text_input(
                "Début (JJ/MM/AAAA)",
                value="01/01/2024"
            )
            date_debut = parse_date_fr(date_debut_input)
            if not date_debut:
                st.error("Format invalide")
                date_debut = date(2024, 1, 1)
        
        with col2:
            date_fin_input = st.text_input(
                "Fin (JJ/MM/AAAA)",
                value=format_date_fr(date.today())
            )
            date_fin = parse_date_fr(date_fin_input)
            if not date_fin:
                st.error("Format invalide")
                date_fin = date.today()
        
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
        
        periode_affichage = f"du {format_date_fr(date_debut)} au {format_date_fr(date_fin)}"
        
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
            
            if articles_complets:
                st.subheader("📚 Articles")
                
                for i, article in enumerate(articles_complets, 1):
                    with st.expander(f"**Article {i}** - {article['title'][:80]}..."):
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
                                st.info("PDF non disponible en libre accès")
            
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

**Critères:** {spec_texte} | {periode_affichage} | {type_etude}

**Articles:**
{contexte}

**PMIDs:** {', '.join(ids)}

Synthèse française:

## 📊 Vue d'ensemble
## 🔬 Tendances
## 💡 Découvertes
## 🏥 Implications
## ⚠️ Limites

## 🔗 Sources
{liens}"""
                    
                    response_ia = model.generate_content(prompt)
                    synthese = response_ia.text
                    
                    st.markdown(synthese)
                    
                    # Section Podcast NotebookLM
                    st.divider()
                    st.subheader("🎙️ Créer un Podcast Audio")
                    
                    st.info("""
💡 **Générer un podcast automatiquement avec NotebookLM :**
1. Téléchargez le fichier optimisé ci-dessous
2. Allez sur [NotebookLM](https://notebooklm.google.com)
3. Créez un nouveau notebook
4. Importez le fichier téléchargé
5. Cliquez sur "Generate Audio Overview"
6. Un podcast conversationnel sera créé automatiquement (durée : 5-15 minutes selon le contenu)
                    """)
                    
                    fichier_notebooklm = generer_fichier_notebooklm(synthese, articles_complets)
                    
                    col_nlm1, col_nlm2 = st.columns(2)
                    
                    with col_nlm1:
                        st.download_button(
                            label="📥 Télécharger pour NotebookLM",
                            data=fichier_notebooklm,
                            file_name=f"notebooklm_veille_{datetime.now().strftime('%Y%m%d')}.txt",
                            mime="text/plain",
                            help="Fichier optimisé pour générer un podcast"
                        )
                    
                    with col_nlm2:
                        st.link_button(
                            label="🔗 Ouvrir NotebookLM",
                            url="https://notebooklm.google.com"
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
                    
                    st.success("✅ Sauvegardé !")
                    
                    st.divider()
                    col1, col2 = st.columns(2)
                    
                    nom = spec_fr if mode_recherche == "Par spécialité" else "recherche"
                    
                    with col1:
                        st.download_button(
                            label="📥 TXT",
                            data=synthese,
                            file_name=f"synthese_{nom}.txt",
                            mime="text/plain"
                        )
                    
                    with col2:
                        with st.spinner("📄 PDF..."):
                            pdf_bytes = generer_pdf_complet(
                                display_term,
                                periode_affichage,
                                len(ids),
                                ids,
                                synthese,
                                articles_complets
                            )
                        st.download_button(
                            label="📄 PDF Complet",
                            data=pdf_bytes,
                            file_name=f"veille_{nom}.pdf",
                            mime="application/pdf"
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
            titre = f"🔍 {rech['date']} - {rech['specialite']} - {rech['nb_articles']} articles"
            
            with st.expander(titre):
                st.markdown(f"**Spécialité:** {rech['specialite']}")
                if rech.get('mots_cles'):
                    st.markdown(f"**Mots-clés:** {rech['mots_cles']}")
                st.markdown(f"**Période:** {rech['periode']}")
                st.markdown(f"**PMIDs:** {', '.join(rech['pmids'])}")
                
                st.divider()
                st.markdown(rech['synthese'])

with tab3:
    st.header("🔗 Sources Complémentaires")
    
    st.markdown("### Sources officielles")
    
    for nom, url in SOURCES_SUPPLEMENTAIRES.items():
        st.markdown(f"**{nom}**")
        st.markdown(f"[Accéder]({url})")
        st.divider()

st.markdown("---")
st.caption("💊 Veille médicale | PubMed + Gemini 2.5")
```

**Requirements.txt mis à jour (SANS PyPDF2) :**
```
streamlit
google-generativeai
requests
fpdf
