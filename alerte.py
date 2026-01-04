import os
import requests
import smtplib
from google import genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURATION ---
GEMINI_KEY = os.getenv("AIzaSyCMPYJIHZ83uVhYwV6eqKxsC1pv7Hbol6g")
PUBMED_API_KEY = os.getenv("17626ab73380b71515000371bdcee0c26308")
EMAIL_SENDER = os.getenv("9f3e72001@smtp-brevo.com")
EMAIL_PW = os.getenv("xsmtpsib-942e7bea4a7ea53de0dad558974e394749186937099494d653498395e8fd1f4a-o60i8GOCOhiQ3SPJ")
EMAIL_RECEIVER = "gregallier66@gmail.com"

def fetch_pubmed_ids(query):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": 5, "api_key": PUBMED_API_KEY}
    try:
        res = requests.get(url, params=params).json()
        return res.get("esearchresult", {}).get("idlist", [])
    except: return []

def envoyer_veille():
    query = "(gynecology[Title] OR obstetrics[Title] OR endocrinology[Title] OR 'general medicine'[Title]) AND (2024:2026[Date - Publication])"
    ids = fetch_pubmed_ids(query)
    
    if not ids:
        print("Aucun article trouvé.")
        return

    liens_html = "".join([f"<li><a href='https://pubmed.ncbi.nlm.nih.gov/{i}/'>Article PubMed {i}</a></li>" for i in ids])

    client = genai.Client(api_key=GEMINI_KEY)
    prompt = f"Tu es un expert médical. Analyse ces articles : {liens_html}. Pour chaque, donne en Français : Titre, Résumé court, Intérêt clinique pour la Gynéco/Endo/MG. Formate le tout proprement en HTML."
    
    try:
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        contenu_ia = response.text.replace("```html", "").replace("```", "") # Nettoyage balises markdown
    except Exception as e:
        contenu_ia = f"Erreur IA : {e}"

    # Construction du mail HTML
    msg = MIMEMultipart("alternative")
    msg['From'] = f"Veille Médicale <{EMAIL_SENDER}>"
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = "Focus Gynéco-Obs / Endo / MG"

    html_body = f"""
    <html>
      <body>
        <h2 style="color: #2e6c80;">Votre Veille Médicale Quotidienne</h2>
        {contenu_ia}
        <hr>
        <p>Sources originales :</p>
        <ul>{liens_html}</ul>
      </body>
    </html>
    """
    msg.attach(MIMEText(html_body, "html"))

    try:
        server = smtplib.SMTP("smtp-relay.brevo.com", 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PW)
        server.send_message(msg)
        server.quit()
        print("✅ Email envoyé avec succès")
    except Exception as e:
        print(f"❌ Erreur SMTP : {e}")

if __name__ == "__main__":
    envoyer_veille()
    
