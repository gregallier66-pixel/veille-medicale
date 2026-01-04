import feedparser
import requests
import smtplib
from google import genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURATION ---
GEMINI_KEY = "AIzaSyCMPYJIHZ83uVhYwV6eqKxsC1pv7Hbol6g"
PUBMED_API_KEY = "17626ab73380b71515000371bdcee0c26308"

# Identifiants Brevo
SMTP_SERVER = "smtp-relay.brevo.com"
SMTP_PORT = 587
EMAIL_SENDER = "9f3e72001@smtp-brevo.com" 
EMAIL_PW = "xsmtpsib-942e7bea4a7ea53de0dad558974e394749186937099494d653498395e8fd1f4a-o60i8GOCOhiQ3SPJ"      # Votre clé finissant par iQ3SPJ
EMAIL_RECEIVER = "gregallier66@gmail.com"

def fetch_pubmed_titles(query):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": 3, "api_key": PUBMED_API_KEY}
    try:
        res = requests.get(url, params=params).json()
        return res.get("esearchresult", {}).get("idlist", [])
    except:
        return []

def envoyer_veille():
    print("Demarrage de la veille...")

    # 1. Collecte des donnees
    flux = feedparser.parse("https://www.who.int/rss-feeds/news-english.xml")
    articles_rss = "\n".join([f"- RSS: {e.title}" for e in flux.entries[:5]])
    pmids = fetch_pubmed_titles("epidemiology")
    articles_pubmed = "\n".join([f"- PubMed ID: {id}" for id in pmids])

    # ON DEFINIT LE PROMPT ICI (Avant l'appel a l'IA)
    donnees_brutes = f"SOURCES RSS :\n{articles_rss}\n\nSOURCES PUBMED :\n{articles_pubmed}"
    texte_prompt = f"Fais un resume court avec emojis (Urgent, Etudes, Infos) de ces actus : {donnees_brutes}"

    # 2. Appel IA
    print("- Analyse par l'IA...")
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        # On utilise gemini-2.0-flash qui est le plus recent et souvent mieux supporte
        response = client.models.generate_content(model="gemini-2.0-flash", contents=texte_prompt)
        resume = response.text
    except Exception as e:
        resume = f"Erreur IA : {e}"

    # 3. ENVOI MAIL
    print("- Envoi du mail...")
    try:
        msg = MIMEMultipart()
        msg['From'] = "gregallier66@gmail.com"
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = "Veille Medicale Reussie"
        msg.attach(MIMEText(resume, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PW)
        server.send_message(msg)
        server.quit()
        print("✅ Tout est bon ! Mail envoye.")
    except Exception as e:
        print(f"❌ Erreur d'envoi : {e}")

if __name__ == "__main__":
    envoyer_veille()
