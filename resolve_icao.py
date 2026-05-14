import json
import os
import zipfile
import urllib.request
import csv

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "jets_africains.json")
OPENSKY_CSV_URL = "https://opensky-network.org/datasets/metadata/aircraftDatabase.csv"
OPENSKY_CSV_PATH = os.path.join(os.path.dirname(__file__), "aircraftDatabase.csv")

def download_database():
    if not os.path.exists(OPENSKY_CSV_PATH):
        print(f"Téléchargement de la base de données OpenSky depuis {OPENSKY_CSV_URL}...")
        try:
            # Add a user-agent to avoid 403 Forbidden
            req = urllib.request.Request(OPENSKY_CSV_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response, open(OPENSKY_CSV_PATH, 'wb') as out_file:
                data = response.read()
                out_file.write(data)
            print("Téléchargement terminé.")
        except Exception as e:
            print(f"Erreur lors du téléchargement: {e}")
            return False
    return True

def resolve_icao():
    if not download_database():
        return

    # Charger le JSON
    with open(DB_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Trouver les avions sans ICAO
    missing_icao = {}
    for country in data:
        for jet in country.get('flotte', []):
            if not jet.get('icao24') and jet.get('tail_number'):
                missing_icao[jet['tail_number'].upper()] = jet

    if not missing_icao:
        print("Aucun avion sans code ICAO trouvé.")
        return

    print(f"Recherche de {len(missing_icao)} codes ICAO...")

    # Scanner le CSV
    found = 0
    with open(OPENSKY_CSV_PATH, 'r', encoding='utf-8', errors='ignore') as csvfile:
        # Le format OpenSky: icao24,registration,manufacturericao,manufacturername,model,typecode,serialnumber,linenumber,icaoaircrafttype,operator,operatorcallsign,operatoricao,operatoriata,owner,testreg,registered,reguntil,status,built,firstflightdate,seatcapacity,engines,icengineclass,enginemodel,emptyweight,maxweight,description,notes,categoryDescription
        reader = csv.DictReader(csvfile)
        for row in reader:
            reg = row.get('registration', '').upper().replace('-', '') # Normaliser (ex: ZSRSA ou ZS-RSA)
            reg_with_dash = row.get('registration', '').upper()
            
            for tail in list(missing_icao.keys()):
                tail_norm = tail.replace('-', '')
                if reg == tail_norm or reg_with_dash == tail:
                    missing_icao[tail]['icao24'] = row['icao24'].lower()
                    missing_icao[tail]['verifie'] = True
                    print(f"Trouve : {tail} -> {row['icao24'].lower()}")
                    found += 1
                    del missing_icao[tail]

    print(f"Résolution terminée : {found} trouvés.")

    # Sauvegarder
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        print("Fichier JSON mis à jour.")

if __name__ == "__main__":
    resolve_icao()
