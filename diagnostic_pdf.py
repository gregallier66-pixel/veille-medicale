"""
Script de diagnostic pour tester la récupération PDF PubMed
Utiliser ce script pour identifier exactement où ça coince
"""

import requests
import xml.etree.ElementTree as ET
from io import BytesIO
import tarfile

def test_pmid(pmid):
    """Test complet pour un PMID"""
    
    print(f"\n{'='*60}")
    print(f"TEST DIAGNOSTIC pour PMID: {pmid}")
    print(f"{'='*60}\n")
    
    # Étape 1: Récupérer DOI et PMCID
    print("ÉTAPE 1: Récupération identifiants...")
    print("-" * 40)
    
    try:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        params = {"db": "pubmed", "id": pmid, "retmode": "xml"}
        
        response = requests.get(base_url, params=params, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ Erreur HTTP: {response.status_code}")
            return
        
        root = ET.fromstring(response.content)
        
        doi = None
        pmcid = None
        
        for article_id in root.findall('.//ArticleId'):
            id_type = article_id.get('IdType')
            if id_type == 'doi':
                doi = article_id.text
            elif id_type == 'pmc':
                pmcid = article_id.text
                if pmcid.startswith('PMC'):
                    pmcid = pmcid[3:]
        
        print(f"✅ DOI: {doi if doi else '❌ NON TROUVÉ'}")
        print(f"✅ PMCID: {pmcid if pmcid else '❌ NON TROUVÉ'}")
        
        if not doi and not pmcid:
            print("\n⚠️ AUCUN identifiant trouvé - Article probablement payant")
            return
        
    except Exception as e:
        print(f"❌ Erreur récupération identifiants: {e}")
        return
    
    # Étape 2: Vérifier disponibilité PDF
    print("\nÉTAPE 2: Vérification disponibilité PDF...")
    print("-" * 40)
    
    try:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
        params = {"dbfrom": "pubmed", "id": pmid, "cmd": "llinks"}
        
        response = requests.get(base_url, params=params, timeout=10)
        
        if "Free in PMC" in response.text or "pmc/articles" in response.text:
            print("✅ PDF GRATUIT détecté par PubMed")
        else:
            print("❌ Aucun PDF gratuit détecté par PubMed")
    
    except Exception as e:
        print(f"❌ Erreur vérification: {e}")
    
    # Étape 3: Test PMC FTP
    if pmcid:
        print("\nÉTAPE 3: Test PMC FTP...")
        print("-" * 40)
        
        try:
            pmcid_num = pmcid
            
            if len(pmcid_num) >= 7:
                dir1 = pmcid_num[-7:-4].zfill(3)
                dir2 = pmcid_num[-4:-1].zfill(3)
            else:
                dir1 = "000"
                dir2 = pmcid_num[-3:].zfill(3)
            
            tar_url = f"https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/{dir1}/{dir2}/PMC{pmcid_num}.tar.gz"
            print(f"URL tar.gz: {tar_url}")
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(tar_url, timeout=30, headers=headers)
            
            print(f"Status Code: {response.status_code}")
            print(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")
            print(f"Content-Length: {len(response.content)} bytes")
            
            if response.status_code == 200:
                print("✅ Fichier tar.gz téléchargé")
                
                # Essayer d'extraire
                try:
                    tar_file = tarfile.open(fileobj=BytesIO(response.content))
                    members = tar_file.getmembers()
                    
                    print(f"✅ Archive contient {len(members)} fichiers:")
                    for member in members:
                        print(f"   - {member.name}")
                        if member.name.endswith('.pdf'):
                            print(f"   ✅ PDF TROUVÉ: {member.name}")
                            pdf_file = tar_file.extractfile(member)
                            pdf_content = pdf_file.read()
                            print(f"   ✅ PDF extrait: {len(pdf_content)} bytes")
                            return True
                except Exception as e:
                    print(f"❌ Erreur extraction tar.gz: {e}")
            else:
                print(f"❌ Échec téléchargement tar.gz")
                
                # Essayer URL directe
                pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid_num}/pdf/"
                print(f"\nTest URL directe: {pdf_url}")
                
                response = requests.get(pdf_url, timeout=20, headers=headers)
                print(f"Status Code: {response.status_code}")
                print(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")
                
                if response.status_code == 200 and 'application/pdf' in response.headers.get('Content-Type', ''):
                    print(f"✅ PDF TROUVÉ via URL directe: {len(response.content)} bytes")
                    return True
                else:
                    print("❌ Échec URL directe")
        
        except Exception as e:
            print(f"❌ Erreur PMC FTP: {e}")
    
    # Étape 4: Test Unpaywall
    if doi:
        print("\nÉTAPE 4: Test Unpaywall...")
        print("-" * 40)
        
        try:
            url = f"https://api.unpaywall.org/v2/{doi}"
            params = {"email": "test@example.com"}
            
            response = requests.get(url, params=params, timeout=15)
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 404:
                print("❌ DOI inconnu d'Unpaywall")
            elif response.status_code == 200:
                data = response.json()
                
                print(f"Open Access: {data.get('is_oa', False)}")
                
                if data.get('is_oa'):
                    best_oa = data.get('best_oa_location')
                    if best_oa:
                        pdf_url = best_oa.get('url_for_pdf')
                        print(f"URL PDF: {pdf_url}")
                        
                        if pdf_url:
                            headers = {'User-Agent': 'Mozilla/5.0'}
                            pdf_response = requests.get(pdf_url, timeout=20, headers=headers)
                            
                            print(f"PDF Status: {pdf_response.status_code}")
                            print(f"PDF Type: {pdf_response.headers.get('Content-Type', 'N/A')}")
                            
                            if pdf_response.status_code == 200 and 'application/pdf' in pdf_response.headers.get('Content-Type', ''):
                                print(f"✅ PDF TROUVÉ via Unpaywall: {len(pdf_response.content)} bytes")
                                return True
                else:
                    print("❌ Article non Open Access")
            else:
                print(f"❌ Erreur Unpaywall: {response.status_code}")
        
        except Exception as e:
            print(f"❌ Erreur Unpaywall: {e}")
    
    # Étape 5: Test Europe PMC
    print("\nÉTAPE 5: Test Europe PMC...")
    print("-" * 40)
    
    try:
        if pmcid:
            pdf_url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid=PMC{pmcid}&blobtype=pdf"
            print(f"URL: {pdf_url}")
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(pdf_url, timeout=20, headers=headers)
            
            print(f"Status Code: {response.status_code}")
            print(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")
            
            if response.status_code == 200 and 'application/pdf' in response.headers.get('Content-Type', ''):
                print(f"✅ PDF TROUVÉ via Europe PMC: {len(response.content)} bytes")
                return True
            else:
                print("❌ Échec Europe PMC")
        
        # API Europe PMC
        api_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {"query": f"EXT_ID:{pmid}", "format": "json", "resultType": "core"}
        
        response = requests.get(api_url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('resultList', {}).get('result', [])
            
            if results:
                result = results[0]
                print(f"Europe PMC ID: {result.get('id', 'N/A')}")
                print(f"Has PDF: {result.get('hasPDF', 'N/A')}")
    
    except Exception as e:
        print(f"❌ Erreur Europe PMC: {e}")
    
    print("\n" + "="*60)
    print("❌ AUCUNE SOURCE N'A FONCTIONNÉ")
    print("="*60)
    return False


# Tests avec des PMIDs connus
if __name__ == "__main__":
    
    print("\n" + "="*60)
    print("DIAGNOSTIC RÉCUPÉRATION PDF PUBMED")
    print("="*60)
    
    # PMIDs de test (articles Open Access connus)
    test_pmids = [
        "33301246",  # Article COVID Open Access récent
        "32203977",  # Article COVID très connu (open access)
        "31257588",  # Article gynéco
    ]
    
    print("\nCe script va tester la récupération PDF pour 3 articles Open Access connus.")
    print("Si AUCUN ne fonctionne, il y a un problème de réseau ou de firewall.\n")
    
    succes = 0
    
    for pmid in test_pmids:
        if test_pmid(pmid):
            succes += 1
    
    print("\n" + "="*60)
    print(f"RÉSULTAT FINAL: {succes}/{len(test_pmids)} PDF récupérés avec succès")
    print("="*60)
    
    if succes == 0:
        print("\n⚠️ DIAGNOSTIC:")
        print("- Vérifiez votre connexion internet")
        print("- Vérifiez que Streamlit Cloud n'a pas de firewall bloquant")
        print("- Essayez d'activer le réseau dans les settings Streamlit")
        print("- Certains hébergeurs bloquent les requêtes vers des sites médicaux")
    elif succes < len(test_pmids):
        print("\n⚠️ DIAGNOSTIC:")
        print("- La récupération fonctionne partiellement")
        print("- Certains articles sont vraiment payants")
        print("- Essayez avec plus d'articles pour améliorer le taux")
    else:
        print("\n✅ TOUT FONCTIONNE!")
        print("Le problème vient probablement des articles sélectionnés (payants).")
