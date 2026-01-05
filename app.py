import streamlit as st
import google.generativeai as genai
import requests
import json

st.set_page_config(page_title="Veille Médicale", layout="wide")

# Récupération de la clé Gemini
try:
    G_KEY = st.secrets["GEMINI_KEY"]
except:
    st.error("⚠️ Clé GEMINI_KEY manquante dans les secrets")
    st.info("Ajoutez votre clé dans Settings → Secrets")
    st.stop()

TRAD = {
    "Gynécologie": "Gynecology", 
    "Endocrinologie": "Endocrinology", 
    "Médecine Générale": "General Medicine"
}

st.title("🩺 Ma Veille Médicale Expert")
st.markdown("*Analyse automatique des dernières publications PubMed*")

with st.sidebar:
    st.header("⚙️ Configuration")
    spec_fr = st.selectbox("Spécialité médicale", list(TRAD.keys()))
    annee = st.radio("Année de publication", ["2024", "2025"])
    nb = st.slider("Nombre d'articles", 1, 10, 5)
    
    st.divider()
    st.caption("🔬 Données: PubMed/NCBI")
    st.caption("🤖 IA: Google Gemini")

if st.button("🔍 Lancer la recherche", type="primary", use_container_width=True):
    
    term = TRAD[spec_fr]
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    
    params = {
        "db": "pubmed",
        "term": f"{term} {annee}",
        "retmode": "json",
        "retmax": nb,
        "sort": "relevance"
    }
    
    # ÉTAPE 1 : Recherche PubMed
    try:
        with st.spinner(f"🔎 Recherche en cours: {term} ({annee})..."):
            response = requests.get(
                base_url,
                params=params,
                headers={'User-Agent': 'Streamlit Medical Research App'},
                timeout=10
            )
        
        if response.status_code != 200:
            st.error(f"❌ Erreur PubMed: {response.status_code}")
            st.stop()
        
        data = response.json()
        search_result = data.get("esearchresult", {})
        ids = search_result.get("idlist", [])
        count = search_result.get("count", "0")
        
        if not ids:
            st.warning(f"⚠️ Aucun article trouvé pour {spec_fr} en {annee}")
            st.info("💡 Essayez une autre année ou spécialité")
            st.stop()
        
        st.success(f"✅ {count} articles trouvés dans PubMed - Affichage de {len(ids)}")
        
        # ÉTAPE 2 : Affichage des articles
        st.subheader("📚 Articles sélectionnés")
        
        cols = st.columns(2)
        for i, pmid in enumerate(ids):
            col = cols[i % 2]
            with col:
                st.markdown(f"""
                **Article {i+1}**  
                🔗 [PubMed ID: {pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)
                """)
        
        st.divider()
        
        # ÉTAPE 3 : Analyse IA avec le BON modèle
        st.subheader("🤖 Synthèse par Intelligence Artificielle")
        
        with st.spinner("⏳ Analyse en cours par Gemini..."):
            try:
                genai.configure(api_key=G_KEY)
                
                # CORRECTION : Utiliser gemini-pro au lieu de gemini-1.5-flash
                model = genai.GenerativeModel('gemini-pro')
                
                liens_articles = "\n".join([f"- https://pubmed.ncbi.nlm.nih.gov/{pmid}/" for pmid in ids])
                
                prompt = f"""Tu es un médecin expert en {spec_fr} réalisant une veille scientifique.

Analyse ces {len(ids)} articles récents de PubMed publiés en {annee}.

**PMIDs analysés:** {', '.join(ids)}

Rédige une synthèse professionnelle structurée en français avec:

## 📊 Vue d'ensemble
Présente le contexte général et la portée de ces publications

## 🔬 Tendances et thématiques principales
Identifie les sujets dominants et les approches innovantes

## 💡 Découvertes et résultats notables
Mets en avant les résultats significatifs et les avancées importantes

## 🏥 Implications pour la pratique clinique
Explique les applications concrètes et recommandations pour les praticiens

## 🔗 Sources
{liens_articles}

Utilise un ton professionnel mais accessible. Sois précis et factuel."""
                
                response_ia = model.generate_content(prompt)
                
                # Afficher la synthèse
                st.markdown(response_ia.text)
                
                # Bouton de téléchargement
                st.download_button(
                    label="📥 Télécharger la synthèse",
                    data=response_ia.text,
                    file_name=f"synthese_{spec_fr}_{annee}.txt",
                    mime="text/plain"
                )
                
            except Exception as e:
                st.error(f"❌ Erreur lors de l'analyse IA: {str(e)}")
                st.info("💡 Les liens vers les articles restent accessibles ci-dessus")
                
                # Afficher les modèles disponibles pour debug
                with st.expander("🔧 Debug: Modèles disponibles"):
                    try:
                        for m in genai.list_models():
                            if 'generateContent' in m.supported_generation_methods:
                                st.write(f"✅ {m.name}")
                    except:
                        pass
    
    except requests.exceptions.Timeout:
        st.error("❌ Délai dépassé - PubMed ne répond pas")
        st.info("Réessayez dans quelques instants")
        
    except Exception as e:
        st.error(f"❌ Erreur technique: {str(e)}")

# Footer
st.markdown("---")
st.caption("💊 Application de veille médicale | Données PubMed + IA Gemini")
