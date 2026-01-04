import os
import requests
import smtplib
from google import genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from fpdf import FPDF

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

def generer_pdf(texte):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        
        # NETTOYAGE ULTIME : On ne garde que les caracteres standards
        # Cela evite l'erreur a la ligne 27
        txt_nettoye = texte.replace('\u2019', "'").replace('\u2013', '-').replace('\u2014', '-')
        txt_final = txt_nettoye.encode('latin-1', 'replace').decode('latin-1')
        
        pdf.multi_cell(0, 10, txt=txt_final)
        pdf.output("report.pdf") # Nom simple
        return True
    except Exception as e:
        print(f"Erreur PDF : {e}")
        return False

def envoyer_veille():
    query = "(gynecology[Title] OR obstetrics[Title] OR endocrinology[Title] OR 'general medicine'[Title]) AND (2024:2026[Date - Publication])"
    ids = fetch_pubmed_ids(query)
    liste_liens = "\n".join([f"https://pubmed.ncbi.nlm.nih.gov/{i}/" for i in ids])

    if not ids:
        print("Aucun article trouvé.")
        return

    client = genai.Client(api_key=GEMINI_KEY)
    # On demande explicitement a l'IA de NE PAS mettre d'emojis
    prompt = f"Tu es medecin. Analyse ces liens : {liste_liens}. Pour chaque : Titre en FR, resume court FR, interet clinique. INTERDIT : Emojis et caracteres speciaux. Termine par les liens."
    
    try:
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        contenu = response.text
    except Exception as e:
        contenu = f"Erreur IA : {e}\n\nLiens :\n{liste_liens}"

    if generer_pdf(contenu):
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = "Veille Medicale Gyneco/Endo"
        msg.attach(MIMEText("Voici votre rapport PDF.", 'plain'))

        if os.path.exists("report.pdf"):
            with open("report.pdf", "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", "attachment; filename=veille.pdf")
                msg.attach(part)

            try:
                server = smtplib.SMTP("smtp-relay.brevo.com", 587)
                server.starttls()
                server.login(EMAIL_SENDER, EMAIL_PW)
                server.send_message(msg)
                server.quit()
                print("✅ Email envoyé avec PDF")
            except Exception as e:
                print(f"❌ Erreur SMTP : {e}")
    else:
        print("❌ Echec PDF")

if __name__ == "__main__":
    envoyer_veille()
