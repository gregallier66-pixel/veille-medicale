import streamlit as st
import google.generativeai as genai
import urllib.request
import urllib.parse
import json

st.set_page_config(page_title="Veille Médicale", layout="wide")

# Récupération des secrets
try:
    G_KEY = st.secrets["GEMINI_KEY"]
    P_KEY = st.secrets["PUBMED_API_KEY"]
except:
    st.error("Erreur de Secrets. Vérifiez les noms GEMINI_KEY et PUBMED_API_KEY.")
    st.stop()

TRAD = {
    "Gynécologie": "Gynecology", 
    "Endocrinologie": "Endocrinology", 
    "Médecine Générale": "General Medicine"
}

st.title("🩺 Ma Veille Médicale Expert")

with st.sidebar:
    st.header("Configuration")
    spec_fr = st.selectbox("Spécialité", list(TRAD.keys()))
    annee = st.radio("Année", ["2024", "2025"])
    nb = st.slider("Articles", 1, 10, 5)

if st.button(f"Lancer la recherche", key="unique_search_button"):
    with st.spinner("Interrogation de PubMed..."):
        term = TRAD[spec_fr]
        
        # Construction de la requête de recherche avec syntaxe correcte
        # Format: terme AND année[PDAT]
        search_query = f"{term} AND {annee}[PDAT]"
        
        # URL de base sans .fcgi
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        
        params = {
            "db": "pubmed",
            "term": search_query,
            "retmode": "json",
            "retmax": str(nb),
            "sort": "relevance"  # Tri par pertinence
        }
        
        # Ajouter la clé API seulement si elle existe et n'est pas vide
        if P_KEY and P_KEY.strip():
            params["api_key"] = P_KEY
        
        # Construction de l'URL
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        
        # Affichage de l'URL pour débogage
        with st.expander("🔍 Voir l'URL de requête"):
            st.code(url)
            st.write("**Paramètres:**")
            st.json(params)
        
        try:
            # Requête avec headers appropriés
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json'
                }
            )
            
            with urllib.request.urlopen(req, timeout=15) as response:
                # Vérifier le code de statut
                if response.status != 200:
                    st.error(f"Erreur HTTP {response.status}")
                    st.stop()
                
                data = json.loads(response.read().decode())
                
                # Afficher la réponse brute pour débogage
                with st.expander("📋 Réponse brute de PubMed"):
                    st.json(data)
                
                ids = data.get("esearchresult", {}).get("idlist", [])
                
                if ids:
                    st.success(f"✅ {len(ids)} articles identifiés")
                    
                    # Affichage des liens PubMed
                    st.subheader("📚 Articles trouvés")
                    for i, pmid in enumerate(ids, 1):
                        st.markdown(f"{i}. [Article PubMed {pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)")
                    
                    # Analyse IA
                    st.subheader("🤖 Analyse par IA")
                    with st.spinner("Génération du résumé..."):
                        try:
                            genai.configure(api_key=G_KEY)
                            model = genai.GenerativeModel('gemini-1.5-flash')
                            
                            liens = [f"https://pubmed.ncbi.nlm.nih.gov/{i}/" for i in ids]
                            prompt = f"""Tu es un expert médical francophone.

Voici {len(ids)} articles récents en {spec_fr} publiés en {annee}.
PMIDs: {', '.join(ids)}

Rédige une synthèse structurée en français comprenant:
1. Les tendances principales observées
2. Les découvertes notables
3. Les implications cliniques potentielles

Liens des articles: {', '.join(liens)}"""
                            
                            res_ia = model.generate_content(prompt)
                            st.markdown(res_ia.text)
                        except Exception as e:
                            st.error(f"Erreur lors de la génération IA: {str(e)}")
                else:
                    st.warning(f"⚠️ Aucun résultat trouvé pour {term} en {annee}.")
                    st.info("💡 Conseil: Essayez une autre année ou spécialité.")
                    
                    # Afficher des suggestions
                    st.write("**Suggestions:**")
                    st.write("- Vérifiez que l'année sélectionnée contient des publications")
                    st.write("- Essayez d'élargir la recherche à plusieurs années")
        
        except urllib.error.HTTPError as e:
            st.error(f"❌ Erreur HTTP {e.code}: {e.reason}")
            
            # Lire le contenu de l'erreur pour plus de détails
            try:
                error_content = e.read().decode()
                with st.expander("Détails de l'erreur"):
                    st.code(error_content)
            except:
                pass
            
            if e.code == 400:
                st.info("🔧 **Erreur 400 - Bad Request**: La requête est mal formée.")
                st.write("Causes possibles:")
                st.write("- Paramètres de recherche invalides")
                st.write("- Clé API incorrecte ou expirée")
                st.write("- Format de date incorrect")
            
        except urllib.error.URLError as e:
            st.error(f"❌ Erreur de connexion: {e.reason}")
            st.info("Vérifiez votre connexion Internet")
            
        except json.JSONDecodeError as e:
            st.error(f"❌ Erreur lors du décodage JSON: {str(e)}")
            st.info("La réponse de PubMed n'est pas au format JSON attendu")
            
        except Exception as e:
            st.error(f"❌ Erreur technique: {type(e).__name__} - {str(e)}")
            import traceback
            with st.expander("Détails techniques"):
                st.code(traceback.format_exc())
