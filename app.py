import streamlit as st
import google.generativeai as genai
import requests
from datetime import datetime, date
import xml.etree.ElementTree as ET
from fpdf import FPDF
import io
import pypdf
from io import BytesIO
import re
import time

st.set_page_config(page_title="Veille Médicale Pro", layout="wide")

# Clés API
try:
    G_KEY = st.secrets["GEMINI_KEY"]
    genai.configure(api_key=G_KEY)
except Exception as e:
    st.error(f"⚠️ Erreur clé GEMINI_KEY: {str(e)}")
    st.stop()

DEEPL_KEY = st.secrets.get("DEEPL_KEY", None)

# Configuration
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
    "Revues systématiques": "Systematic Review"
}

JOURNAUX_SPECIALITE = {
    "Gynécologie": ["BJOG", "Obstet Gynecol", "Am J Obstet Gynecol", "Hum Reprod", "Fertil Steril"],
    "Obstétrique": ["BJOG", "Obstet Gynecol", "Am J Obstet Gynecol", "Ultrasound Obstet Gynecol"],
    "Anesthésie-Réanimation": ["Anesthesiology", "Br J Anaesth", "Anesth Analg"],
    "Endocrinologie": ["J Clin Endocrinol Metab", "Diabetes Care", "Eur J Endocrinol"],
    "Médecine Générale": ["BMJ", "JAMA", "N Engl J Med", "Lancet"],
    "Chirurgie Gynécologique": ["Gynecol Surg", "J Minim Invasive Gynecol"],
    "Infertilité": ["Fertil Steril", "Hum Reprod"],
    "Échographie Gynécologique": ["Ultrasound Obstet Gynecol", "J Ultrasound Med"],
    "Oncologie": ["J Clin Oncol", "Lancet Oncol", "Cancer"],
    "Pédiatrie": ["Pediatrics", "JAMA Pediatr"]
}

# Session state
for key in ['articles_previsualises', 'mode_etape', 'info_recherche', 'analyses_individuelles', 'fichiers_finaux']:
    if key not in st.session_state:
        st.session_state[key] = [] if key == 'articles_previsualises' else ({} if key != 'mode_etape' else 1)

# Fonctions utilitaires
def nettoyer_titre(titre):
    if not titre:
        return "Titre non disponible"
    titre = re.sub(r'<[^>]+>', '', titre)
    titre = re.sub(r'see\s+more', '', titre, flags=re.IGNORECASE)
    titre = re.sub(r'\s+', ' ', titre)
    return titre.strip()

def traduire_texte(texte, mode="gemini"):
    if not texte or len(texte) < 3:
        return texte
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(f"Traduis en français: {texte}")
        trad = response.text.strip().replace("**", "").replace("Traduction:", "")
        return nettoyer_titre(trad)
    except:
        return texte

def traduire_mots_cles(mots):
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        prompt = f"""Traduis en anglais médical pour PubMed (terminologie MeSH).
UNIQUEMENT le terme anglais, sans explication.

Exemples:
dysménorrhée → dysmenorrhea
hypertension gravidique → gestational hypertension

Terme: {mots}
Anglais:"""
        response = model.generate_content(prompt)
        return response.text.strip().replace('"', '').replace("'", "")
    except:
        return mots

def obtenir_liens_pdf(pmid):
    try:
        urls = []
        # efetch
        r = requests.get(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmid}&retmode=xml", timeout=10)
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            pmc = root.find('.//ArticleId[@IdType="pmc"]')
            if pmc is not None:
                pmc_id = pmc.text.replace("PMC", "")
                urls.extend([
                    f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/",
                    f"https://europepmc.org/articles/PMC{pmc_id}?pdf=render"
                ])
            doi = root.find('.//ArticleId[@IdType="doi"]')
            if doi is not None:
                urls.append(f"https://doi.org/{doi.text}")
        return urls
    except:
        return []

def telecharger_pdf(pmid, progress_callback=None):
    try:
        urls = obtenir_liens_pdf(pmid)
        if not urls:
            return None, "PDF non disponible"
        
        if progress_callback:
            progress_callback(f"📥 Téléchargement...")
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0'}
        
        for url in urls:
            try:
                r = requests.get(url, timeout=30, headers=headers, allow_redirects=True)
                if r.status_code == 200 and (b'%PDF' in r.content[:10] or 'pdf' in r.headers.get('Content-Type', '')):
                    if progress_callback:
                        progress_callback("📄 Extraction...")
                    
                    pdf = pypdf.PdfReader(BytesIO(r.content))
                    texte = ""
                    for i in range(min(len(pdf.pages), 15)):
                        try:
                            texte += pdf.pages[i].extract_text() + "\n\n"
                        except:
                            continue
                    
                    if len(texte) < 100:
                        continue
                    
                    if len(texte) > 12000:
                        texte = texte[:12000]
                    
                    if progress_callback:
                        progress_callback("🌐 Traduction...")
                    
                    trad = ""
                    for i in range(0, len(texte), 4000):
                        trad += traduire_texte(texte[i:i+4000]) + "\n\n"
                    
                    return trad, None
            except:
                continue
        
        return None, "PDF non accessible"
    except Exception as e:
        return None, str(e)

def recuperer_titres(pmids, traduire=False):
    try:
        r = requests.get(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={','.join(pmids)}&retmode=xml", timeout=15)
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            articles = []
            for art in root.findall('.//PubmedArticle'):
                pmid = art.find('.//PMID')
                pmid = pmid.text if pmid is not None else "N/A"
                
                titre_elem = art.find('.//ArticleTitle')
                titre = ''.join(titre_elem.itertext()) if titre_elem is not None else "N/A"
                titre = nettoyer_titre(titre)
                
                titre_fr = traduire_texte(titre) if traduire else titre
                titre_fr = nettoyer_titre(titre_fr)
                
                journal = art.find('.//Journal/Title')
                journal = journal.text if journal is not None else "N/A"
                
                year = art.find('.//PubDate/Year')
                year = year.text if year is not None else "N/A"
                
                articles.append({
                    'pmid': pmid,
                    'title_fr': titre_fr,
                    'journal': journal,
                    'year': year
                })
            return articles
    except:
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

def generer_pdf(spec, periode, articles):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 20)
    pdf.cell(0, 15, 'VEILLE MEDICALE', 0, 1, 'C')
    pdf.ln(10)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, f'Specialite: {spec}', 0, 1, 'C')
    
    for i, a in enumerate(articles, 1):
        pdf.add_page()
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, f'Article {i} - PMID {a["pmid"]}', 0, 1)
        pdf.set_font('Arial', '', 10)
        try:
            t = a['title_fr'].encode('latin-1', 'ignore').decode('latin-1')
        except:
            t = a['title_fr'].encode('ascii', 'ignore').decode('ascii')
        pdf.multi_cell(0, 5, t)
    
    out = io.BytesIO()
    pdf.output(dest='S').encode('latin-1')
    out.write(pdf.output(dest='S').encode('latin-1'))
    out.seek(0)
    return out.getvalue()

def generer_notebooklm(articles):
    txt = f"# VEILLE MEDICALE\nDate: {datetime.now().strftime('%d/%m/%Y')}\n\n"
    for i, a in enumerate(articles, 1):
        txt += f"### Article {i}\n{a['title_fr']}\nPMID: {a['pmid']}\n\n{a.get('pdf_texte_fr', '')}\n---\n"
    return txt

# Interface
st.title("🩺 Veille Médicale Professionnelle")

tab1, tab2 = st.tabs(["🔍 Recherche", "⚙️ Config"])

with tab1:
    if st.session_state.mode_etape == 1:
        st.header("📋 Recherche")
        
        with st.sidebar:
            st.header("⚙️ Paramètres")
            
            mode = st.radio("Mode", ["Par spécialité", "Par mots-clés"])
            
            if mode == "Par spécialité":
                spec = st.selectbox("Spécialité", list(TRAD.keys()))
                mots = ""
                spec_combo = None
                
                st.subheader("Journaux")
                choix_j = st.radio("Limiter à:", ["Tous PubMed", "Journaux spécialité", "Un journal"])
                
                if choix_j == "Un journal":
                    journal = st.selectbox("Journal:", JOURNAUX_SPECIALITE[spec])
                elif choix_j == "Journaux spécialité":
                    journal = "SPECIALITE"
                else:
                    journal = "TOUS"
            else:
                spec = None
                mots = st.text_area("Mots-clés", height=80)
                
                cibler = st.checkbox("🔬 Cibler spécialité")
                if cibler:
                    spec_combo = st.selectbox("Spécialité:", list(TRAD.keys()))
                    st.subheader("Journaux")
                    choix_j = st.radio("Limiter à:", ["Tous PubMed", "Journaux spécialité", "Un journal"])
                    
                    if choix_j == "Un journal":
                        journal = st.selectbox("Journal:", JOURNAUX_SPECIALITE[spec_combo])
                    elif choix_j == "Journaux spécialité":
                        journal = "SPECIALITE"
                    else:
                        journal = "TOUS"
                else:
                    spec_combo = None
                    journal = "TOUS"
            
            st.subheader("Période")
            d1 = st.date_input("Début", value=date(2024, 1, 1), format="DD/MM/YYYY")
            d2 = st.date_input("Fin", value=date.today(), format="DD/MM/YYYY")
            
            st.subheader("Filtres")
            pdf_only = st.checkbox("PDF complets uniquement", value=True)
            type_e = st.selectbox("Type", list(TYPES_ETUDE.keys()))
            nb = st.slider("Max", 10, 200, 50, 10)
            trad = st.checkbox("Traduire titres", value=True)
        
        if st.button("🔍 LANCER", type="primary", use_container_width=True):
            if mode == "Par spécialité":
                term = TRAD[spec]
                display = spec
                spec_used = spec
            else:
                if not mots:
                    st.error("⚠️ Entrez mots-clés")
                    st.stop()
                
                with st.spinner("Traduction..."):
                    term = traduire_mots_cles(mots)
                
                with st.expander("🔍 Traduction"):
                    st.write(f"**FR:** {mots}")
                    st.write(f"**EN:** {term}")
                
                display = f"Mots: {mots}"
                
                if cibler and spec_combo:
                    term = f"{term} AND {TRAD[spec_combo]}"
                    spec_used = spec_combo
                else:
                    spec_used = "Personnalisé"
            
            query_parts = [term]
            query_parts.append(f"{d1.strftime('%Y/%m/%d')}:{d2.strftime('%Y/%m/%d')}[pdat]")
            
            if pdf_only:
                query_parts.append("free full text[sb]")
            
            if journal == "SPECIALITE":
                journaux = JOURNAUX_SPECIALITE.get(spec_used, [])
                if journaux:
                    jq = " OR ".join([f'"{j}"[Journal]' for j in journaux])
                    query_parts.append(f"({jq})")
            elif journal != "TOUS":
                query_parts.append(f'"{journal}"[Journal]')
            
            if TYPES_ETUDE[type_e]:
                query_parts.append(f"{TYPES_ETUDE[type_e]}[ptyp]")
            
            query = " AND ".join(query_parts)
            
            with st.expander("🔍 Requête PubMed"):
                st.code(query)
            
            try:
                with st.spinner("Recherche..."):
                    r = requests.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", 
                                   params={"db": "pubmed", "term": query, "retmode": "json", "retmax": nb}, 
                                   timeout=15)
                
                if r.status_code != 200:
                    st.error(f"Erreur: {r.status_code}")
                    st.stop()
                
                data = r.json()
                ids = data.get("esearchresult", {}).get("idlist", [])
                count = data.get("esearchresult", {}).get("count", "0")
                
                if not ids:
                    st.warning("⚠️ Aucun résultat")
                    st.info("Élargissez la période ou retirez les filtres")
                    st.stop()
                
                st.success(f"✅ {count} articles - {len(ids)} affichés")
                
                with st.spinner("Récupération..."):
                    articles = recuperer_titres(ids, traduire=trad)
                
                st.session_state.articles_previsualises = articles
                st.session_state.info_recherche = {
                    'display_term': display,
                    'periode': f"{d1.strftime('%d/%m/%Y')} - {d2.strftime('%d/%m/%Y')}",
                    'spec': spec_used
                }
                
                st.session_state.mode_etape = 2
                st.rerun()
            except Exception as e:
                st.error(f"Erreur: {str(e)}")
    
    elif st.session_state.mode_etape == 2:
        st.header("📑 Sélection")
        
        st.info(f"{st.session_state.info_recherche['display_term']} | {st.session_state.info_recherche['periode']}")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Tout"):
                for i in range(len(st.session_state.articles_previsualises)):
                    st.session_state[f"s_{i}"] = True
                st.rerun()
        with c2:
            if st.button("↩️ Nouvelle"):
                st.session_state.mode_etape = 1
                st.session_state.articles_previsualises = []
                st.rerun()
        
        st.divider()
        
        sel = []
        for i, a in enumerate(st.session_state.articles_previsualises):
            cc, ci = st.columns([0.1, 0.9])
            with cc:
                s = st.checkbox("", key=f"s_{i}", label_visibility="collapsed")
            with ci:
                st.markdown(f"**{i+1}. {a['title_fr']}**")
                st.markdown(f"📰 {a['journal']} | {a['year']} | [PMID {a['pmid']}](https://pubmed.ncbi.nlm.nih.gov/{a['pmid']}/)")
            
            if s:
                sel.append(a['pmid'])
            st.divider()
        
        st.markdown(f"**{len(sel)} sélectionné(s)**")
        
        if 0 < len(sel) <= 20:
            if st.button("🚀 ANALYSER", type="primary", use_container_width=True):
                st.session_state.analyses_individuelles = {}
                
                for idx, pmid in enumerate(sel):
                    st.subheader(f"📄 Article {idx+1}/{len(sel)}")
                    
                    a_info = next((a for a in st.session_state.articles_previsualises if a['pmid'] == pmid), None)
                    if not a_info:
                        continue
                    
                    st.markdown(f"**{a_info['title_fr']}**")
                    st.markdown(f"[🔗 PubMed](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)")
                    
                    status = st.empty()
                    pdf_txt, err = telecharger_pdf(pmid, progress_callback=lambda m: status.info(m))
                    status.empty()
                    
                    if pdf_txt:
                        st.success(f"✅ PDF extrait ({len(pdf_txt)} car.)")
                        
                        with st.expander("📄 PDF"):
                            st.text_area("", pdf_txt, height=400, key=f"p_{pmid}")
                        
                        with st.spinner("🤖 Analyse..."):
                            try:
                                model = genai.GenerativeModel('gemini-2.0-flash-exp')
                                analyse = model.generate_content(f"Analyse médicale.\n\n{a_info['title_fr']}\n\n{pdf_txt}\n\nAnalyse:\n## Objectif\n## Méthodologie\n## Résultats\n## Conclusion").text
                                
                                st.markdown("### 🤖 Analyse")
                                st.markdown(analyse)
                                
                                st.session_state.analyses_individuelles[pmid] = {
                                    'pmid': pmid,
                                    'title_fr': a_info['title_fr'],
                                    'journal': a_info['journal'],
                                    'year': a_info['year'],
                                    'pdf_texte_fr': pdf_txt,
                                    'analyse_ia': analyse
                                }
                            except Exception as e:
                                st.error(f"Erreur: {e}")
                    else:
                        st.error(f"❌ {err}")
                    
                    st.divider()
                
                if st.session_state.analyses_individuelles:
                    st.session_state.mode_etape = 3
                    st.rerun()
    
    elif st.session_state.mode_etape == 3:
        st.header("📚 Sélection finale")
        
        final = []
        for pmid, data in st.session_state.analyses_individuelles.items():
            cc, ci = st.columns([0.1, 0.9])
            with cc:
                inc = st.checkbox("", key=f"f_{pmid}", value=True, label_visibility="collapsed")
            with ci:
                st.markdown(f"**{data['title_fr']}**")
                with st.expander("🤖 Analyse"):
                    st.markdown(data['analyse_ia'])
            
            if inc:
                final.append(pmid)
            st.divider()
        
        if final:
            st.success(f"✅ {len(final)} sélectionné(s)")
            
            if st.button("📦 GÉNÉRER", type="primary", use_container_width=True):
                arts = [st.session_state.analyses_individuelles[p] for p in final]
                
                with st.spinner("Génération..."):
                    pdf = generer_pdf(st.session_state.info_recherche['spec'], st.session_state.info_recherche['periode'], arts)
                    txt = generer_notebooklm(arts)
                
                st.session_state.fichiers_finaux = {'pdf': pdf, 'notebooklm': txt, 'articles': arts}
                st.session_state.mode_etape = 4
                st.rerun()
    
    elif st.session_state.mode_etape == 4:
        st.header("🎉 Terminé!")
        
        st.success(f"✅ {len(st.session_state.fichiers_finaux['articles'])} articles")
        
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("📄 PDF", st.session_state.fichiers_finaux['pdf'], f"veille_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf", use_container_width=True)
        with c2:
            st.download_button("🎙️ NotebookLM", st.session_state.fichiers_finaux['notebooklm'], f"podcast_{datetime.now().strftime('%Y%m%d')}.txt", use_container_width=True)
        
        st.link_button("🔗 NotebookLM", "https://notebooklm.google.com", use_container_width=True)
        
        if st.button("🔄 Nouvelle", use_container_width=True):
            st.session_state.mode_etape = 1
            st.session_state.articles_previsualises = []
            st.session_state.analyses_individuelles = {}
            st.session_state.fichiers_finaux = {}
            st.rerun()

with tab2:
    st.header("⚙️ Configuration")
    st.info("Gemini 2.0 Flash actif")

st.caption("💊 Veille médicale | Gemini 2.0 Flash")
