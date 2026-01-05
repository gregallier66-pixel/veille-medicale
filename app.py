import streamlit as st
import google.generativeai as genai
import requests
import json
from datetime import datetime
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

# Initialiser l'historique dans session_state
if 'historique' not in st.session_state:
    st.session_state.historique = []

# Fonction pour traduire les mots-clés français en anglais
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
        st.warning(f"⚠️ Traduction automatique échouée, utilisation des termes originaux")
        return mots_cles_fr

# Fonction pour traduire un texte avec Gemini
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
        return f"[Erreur de traduction: {str(e)}]"

# Fonction pour créer un PDF
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Veille Medicale - Synthese IA', 0, 1, 'C')
        self.ln(5)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
    
    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(2)
    
    def chapter_body(self, body):
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 5, body)
        self.ln()

def generer_pdf(spec, annee, nb_articles, pmids, synthese):
    """Génère un PDF de la synthèse"""
    pdf = PDF()
    pdf.add_page()
    
    # Informations de recherche
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 10, f'Specialite: {spec}', 0, 1)
    pdf.cell(0, 10, f'Annee: {annee}', 0, 1)
    pdf.cell(0, 10, f'Nombre d\'articles: {nb_articles}', 0, 1)
    pdf.cell(0, 10, f'Date: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1)
    pdf.ln(5)
    
    # PMIDs
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 10, 'Articles analyses (PMIDs):', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 5, ', '.join(pmids))
    pdf.ln(5)
    
    # Synthèse
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Synthese par Intelligence Artificielle', 0, 1)
    pdf.ln(2)
    
    # Encoder le texte en latin-1 (simple) pour éviter les erreurs unicode
    try:
        synthese_clean = synthese.encode('latin-1', 'ignore').decode('latin-1')
    except:
        synthese_clean = synthese.encode('ascii', 'ignore').decode('ascii')
    
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 5, synthese_clean)
    
    # Sauvegarder en mémoire
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
                
                # Traduire si demandé
                abstract_fr = abstract
                if traduire and abstract != "Résumé non disponible" and api_key:
                    abstract_fr = traduire_texte(abstract, api_key)
                
                # Auteurs
                authors = []
                for author in article.findall('.//Author'):
                    lastname = author.find('LastName')
                    forename = author.find('ForeName')
                    if lastname is not None:
                        name = lastname.text
                        if forename is not None:
                            name = f"{forename.text} {name}"
                        authors.append(name)
                
                # Journal
                journal_elem = article.find('.//Journal/Title')
                journal = journal_elem.text if journal_elem is not None else "Journal non disponible"
                
                # Année
                year_elem = article.find('.//PubDate/Year')
                year = year_elem.text if year_elem is not None else "N/A"
                
                articles_data.append({
                    'pmid': pmid,
                    'title': title,
                    'abstract': abstract,
                    'abstract_fr': abstract_fr,
                    'authors': authors[:3],  # 3 premiers auteurs
                    'journal': journal,
                    'year': year
                })
            
            return articles_data
    except Exception as e:
        st.warning(f"Erreur lors de la récupération des résumés: {str(e)}")
        return []
    
    return []

def sauvegarder_recherche(spec, annee, type_etude, langue, pmids, synthese, mots_cles=""):
    """Sauvegarde la recherche dans l'historique"""
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
    st.session_state.historique.insert(0, recherche)  # Ajouter en première position
    # Garder seulement les 20 dernières recherches
    if len(st.session_state.historique) > 20:
        st.session_state.historique = st.session_state.historique[:20]

# Interface principale
st.title("🩺 Veille Médicale Professionnelle")
st.markdown("*Analyse avancée des publications PubMed avec IA*")

# Tabs pour organiser l'interface
tab1, tab2 = st.tabs(["🔍 Nouvelle Recherche", "📚 Historique"])

with tab1:
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Mode de recherche
        mode_recherche = st.radio("Mode de recherche", ["Par spécialité", "Par mots-clés"], horizontal=True)
        
        if mode_recherche == "Par spécialité":
            spec_fr = st.selectbox("🏥 Spécialité médicale", list(TRAD.keys()))
            mots_cles_custom = ""
            mots_cles_originaux = ""
        else:
            spec_fr = None
            mots_cles_custom = st.text_area(
                "🔎 Mots-clés de recherche",
                placeholder="Exemples:\n- diabète de type 2 traitement\n- cancer du sein immunothérapie\n- hypertension artérielle nouvelles recommandations",
                help="Entrez vos mots-clés en français ou en anglais. Séparez-les par des virgules ou sur des lignes différentes.",
                height=100
            )
            mots_cles_originaux = mots_cles_custom
        
        st.subheader("📅 Période")
        col1, col2 = st.columns(2)
        with col1:
            annee_debut = st.selectbox("De", ["2020", "2021", "2022", "2023", "2024", "2025"], index=4)
        with col2:
            annee_fin = st.selectbox("À", ["2020", "2021", "2022", "2023", "2024", "2025"], index=4)
        
        st.subheader("🔬 Filtres avancés")
        type_etude = st.selectbox("Type d'étude", list(TYPES_ETUDE.keys()))
        
        langue = st.selectbox("Langue", [
            "Toutes",
            "Anglais",
            "Français",
            "Espagnol",
            "Allemand"
        ])
        
        # Option de traduction
        traduire_abstracts = st.checkbox("🌐 Traduire les résumés en français", value=True)
        
        nb = st.slider("📊 Nombre d'articles", 1, 20, 5)
        
        st.divider()
        st.caption("🔬 Données: PubMed/NCBI")
        st.caption("🤖 IA: Google Gemini 2.5")
        st.caption("🌐 Traduction automatique FR↔EN")

    if st.button("🔍 Lancer la recherche", type="primary", use_container_width=True):
        
        # Validation
        if mode_recherche == "Par mots-clés" and not mots_cles_custom:
            st.error("⚠️ Veuillez entrer des mots-clés de recherche")
            st.stop()
        
        # Construction de la requête
        if mode_recherche == "Par spécialité":
            term = TRAD[spec_fr]
            display_term = spec_fr
            mots_cles_traduits = None
        else:
            # Traduire les mots-clés français en anglais
            with st.spinner("🌐 Traduction des mots-clés en anglais médical..."):
                mots_cles_traduits = traduire_mots_cles(mots_cles_custom, G_KEY)
            
            term = mots_cles_traduits
            display_term = f"Mots-clés: {mots_cles_custom}"
            
            # Afficher la traduction
            st.info(f"🔄 **Traduction pour PubMed:** {mots_cles_traduits}")
        
        # Construction de la requête avec filtres
        query_parts = [term]
        
        # Filtre de période
        if annee_debut == annee_fin:
            query_parts.append(f"{annee_debut}[pdat]")
        else:
            query_parts.append(f"{annee_debut}:{annee_fin}[pdat]")
        
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
        
        # Afficher la requête
        with st.expander("🔍 Détails de la requête PubMed"):
            st.write(f"**Recherche:** {display_term}")
            if mots_cles_traduits:
                st.write(f"**Mots-clés originaux (FR):** {mots_cles_custom}")
                st.write(f"**Mots-clés traduits (EN):** {mots_cles_traduits}")
            st.code(query)
        
        # ÉTAPE 1 : Recherche PubMed
        try:
            with st.spinner(f"🔎 Recherche en cours sur PubMed..."):
                response = requests.get(
                    base_url,
                    params=params,
                    headers={'User-Agent': 'Streamlit Medical Research App'},
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
                st.warning(f"⚠️ Aucun article trouvé avec ces critères")
                st.info("💡 **Suggestions:**")
                st.write("- Essayez des mots-clés plus généraux")
                st.write("- Élargissez la période de recherche")
                st.write("- Retirez certains filtres avancés")
                st.stop()
            
            st.success(f"✅ {count} articles trouvés - Affichage de {len(ids)}")
            
            # ÉTAPE 2 : Récupération des résumés complets
            message_traduction = "📄 Récupération et traduction des résumés..." if traduire_abstracts else "📄 Récupération des résumés..."
            with st.spinner(message_traduction):
                articles_complets = recuperer_abstracts(ids, traduire=traduire_abstracts, api_key=G_KEY)
            
            if articles_complets:
                st.subheader("📚 Articles avec résumés")
                
                for i, article in enumerate(articles_complets, 1):
                    with st.expander(f"**Article {i}** - {article['title'][:100]}..."):
                        st.markdown(f"**PMID:** [{article['pmid']}](https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/)")
                        st.markdown(f"**Journal:** {article['journal']} ({article['year']})")
                        if article['authors']:
                            st.markdown(f"**Auteurs:** {', '.join(article['authors'])}")
                        
                        # Afficher résumé traduit ou original
                        if traduire_abstracts:
                            st.markdown("**📖 Résumé (Français):**")
                            st.write(article['abstract_fr'])
                            
                            with st.expander("🔤 Voir le résumé original (Anglais)"):
                                st.write(article['abstract'])
                        else:
                            st.markdown("**📖 Résumé:**")
                            st.write(article['abstract'])
            else:
                st.subheader("📚 Articles sélectionnés")
                cols = st.columns(2)
                for i, pmid in enumerate(ids):
                    col = cols[i % 2]
                    with col:
                        st.markdown(f"**{i+1}.** [PubMed ID: {pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)")
            
            st.divider()
            
            # ÉTAPE 3 : Analyse IA enrichie avec les abstracts
            st.subheader("🤖 Synthèse par Intelligence Artificielle")
            
            with st.spinner("⏳ Analyse approfondie en cours..."):
                try:
                    genai.configure(api_key=G_KEY)
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    # Préparer le contexte avec les abstracts (en français si traduits)
                    contexte_articles = ""
                    if articles_complets:
                        for art in articles_complets:
                            resume_a_utiliser = art['abstract_fr'] if traduire_abstracts else art['abstract']
                            contexte_articles += f"\n\nPMID {art['pmid']}:\nTitre: {art['title']}\nRésumé: {resume_a_utiliser}\n"
                    
                    liens_articles = "\n".join([f"- https://pubmed.ncbi.nlm.nih.gov/{pmid}/" for pmid in ids])
                    
                    specialite_texte = spec_fr if mode_recherche == "Par spécialité" else f"Recherche par mots-clés: {mots_cles_custom}"
                    
                    prompt = f"""Tu es un médecin expert réalisant une veille scientifique approfondie.

Analyse ces {len(ids)} articles récents de PubMed.

**Critères de recherche:**
- {specialite_texte}
- Période: {annee_debut} à {annee_fin}
- Type d'étude: {type_etude}
- Langue: {langue}

**Articles avec résumés complets:**
{contexte_articles}

**PMIDs:** {', '.join(ids)}

Rédige une synthèse professionnelle détaillée en français avec:

## 📊 Vue d'ensemble
Présente le contexte général, la méthodologie des études et leur portée

## 🔬 Tendances et thématiques principales
Identifie les sujets dominants, les approches innovantes et les paradigmes émergents

## 💡 Découvertes et résultats notables
Détaille les résultats significatifs, les avancées importantes et les données clés

## 🏥 Implications pour la pratique clinique
Explique les applications concrètes, recommandations pratiques et impact sur les protocoles

## ⚠️ Limites et perspectives
Mentionne les limites méthodologiques et les axes de recherche futurs

## 🔗 Sources
{liens_articles}

Utilise un ton professionnel, scientifique mais accessible. Cite les PMIDs pertinents pour chaque point important."""
                    
                    response_ia = model.generate_content(prompt)
                    synthese_texte = response_ia.text
                    
                    # Afficher la synthèse
                    st.markdown(synthese_texte)
                    
                    # Sauvegarder dans l'historique
                    sauvegarder_recherche(
                        spec_fr if mode_recherche == "Par spécialité" else "Recherche personnalisée",
                        f"{annee_debut}-{annee_fin}",
                        type_etude,
                        langue,
                        ids,
                        synthese_texte,
                        mots_cles_originaux
                    )
                    
                    st.success("✅ Synthèse générée et sauvegardée !")
                    
                    # Boutons de téléchargement
                    col1, col2 = st.columns(2)
                    
                    nom_fichier = spec_fr if mode_recherche == "Par spécialité" else "recherche_personnalisee"
                    
                    with col1:
                        st.download_button(
                            label="📥 Télécharger (.txt)",
                            data=synthese_texte,
                            file_name=f"synthese_{nom_fichier}_{annee_debut}-{annee_fin}.txt",
                            mime="text/plain"
                        )
                    
                    with col2:
                        # Générer le PDF
                        pdf_bytes = generer_pdf(display_term, f"{annee_debut}-{annee_fin}", len(ids), ids, synthese_texte)
                        st.download_button(
                            label="📄 Télécharger (PDF)",
                            data=pdf_bytes,
                            file_name=f"synthese_{nom_fichier}_{annee_debut}-{annee_fin}.pdf",
                            mime="application/pdf"
                        )
                    
                except Exception as e:
                    st.error(f"❌ Erreur lors de l'analyse IA: {str(e)}")
                    st.info("💡 Les articles et résumés restent accessibles ci-dessus")
        
        except requests.exceptions.Timeout:
            st.error("❌ Délai dépassé - PubMed ne répond pas")
            st.info("Réessayez dans quelques instants")
            
        except Exception as e:
            st.error(f"❌ Erreur technique: {str(e)}")

with tab2:
    st.header("📚 Historique des recherches")
    
    if not st.session_state.historique:
        st.info("Aucune recherche enregistrée pour le moment.")
    else:
        st.write(f"**{len(st.session_state.historique)} recherche(s) sauvegardée(s)**")
        
        for i, rech in enumerate(st.session_state.historique):
            titre_historique = f"🔍 {rech['date']} - {rech['specialite']} ({rech['annee']}) - {rech['nb_articles']} articles"
            if rech.get('mots_cles'):
                titre_historique += f" - Mots-clés: {rech['mots_cles'][:50]}..."
            
            with st.expander(titre_historique):
                st.markdown(f"**Spécialité:** {rech['specialite']}")
                if rech.get('mots_cles'):
                    st.markdown(f"**Mots-clés:** {rech['mots_cles']}")
                st.markdown(f"**Année:** {rech['annee']}")
                st.markdown(f"**Type d'étude:** {rech['type_etude']}")
                st.markdown(f"**Langue:** {rech['langue']}")
                st.markdown(f"**Nombre d'articles:** {rech['nb_articles']}")
                st.markdown(f"**PMIDs:** {', '.join(rech['pmids'])}")
                
                st.divider()
                st.markdown("**Synthèse IA:**")
                st.markdown(rech['synthese'])
                
                # Boutons de téléchargement pour l'historique
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.download_button(
                        label="📥 TXT",
                        data=rech['synthese'],
                        file_name=f"synthese_historique_{i+1}.txt",
                        mime="text/plain",
                        key=f"txt_{i}"
                    )
                
                with col2:
                    pdf_bytes = generer_pdf(rech['specialite'], rech['annee'], rech['nb_articles'], rech['pmids'], rech['synthese'])
                    st.download_button(
                        label="📄 PDF",
                        data=pdf_bytes,
                        file_name=f"synthese_historique_{i+1}.pdf",
                        mime="application/pdf",
                        key=f"pdf_{i}"
                    )
                
                with col3:
                    liens = "\n".join([f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" for pmid in rech['pmids']])
                    st.download_button(
                        label="🔗 Liens",
                        data=liens,
                        file_name=f"liens_articles_{i+1}.txt",
                        mime="text/plain",
                        key=f"liens_{i}"
                    )
        
        st.divider()
        if st.button("🗑️ Effacer l'historique", type="secondary"):
            st.session_state.historique = []
            st.success("Historique effacé !")
            st.rerun()

# Footer
st.markdown("---")
st.caption("💊 Application de veille médicale professionnelle | PubMed + Gemini 2.5 | 🌐 Traduction FR↔EN automatique")
