import os
import re
import csv
from duckduckgo_search import DDGS

def find_vip_jet(vip_name: str) -> dict:
    """
    Tente de trouver automatiquement le jet privé d'une personnalité.
    Retourne un dict avec icao24, tail_number, description s'il est trouvé.
    """
    # 1. Recherche DuckDuckGo
    queries = [
        f'"{vip_name}" private jet registration',
        f'"{vip_name}" private jet "tail number"',
        f'"{vip_name}" private jet N-number'
    ]
    
    results = []
    try:
        ddgs = DDGS()
        for q in queries:
            res = list(ddgs.text(q, max_results=3))
            results.extend(res)
    except Exception as e:
        print(f"Erreur DuckDuckGo: {e}")
        return None
        
    if not results:
        return None
        
    # Combinaison de tout le texte des résultats
    text_content = " ".join([r.get("body", "") + " " + r.get("title", "") for r in results]).upper()
    
    # 2. Extraction d'immatriculations potentielles via Regex
    # Modèles courants: N-number (US), F-XXXX (France), G-XXXX (UK), D-XXXX (Allemagne), etc.
    # Exclure les faux positifs communs
    regex_pattern = r'\b(N[1-9][0-9]{0,4}[A-Z]{0,2}|[A-Z]{1,2}-[A-Z0-9]{3,5}|[0-9]{1}[A-Z]{1}-[A-Z0-9]{3,5})\b'
    
    potential_tails = re.findall(regex_pattern, text_content)
    # Retirer les doublons et mots communs qui matchent la regex par erreur (ex: E-MAIL)
    false_positives = ["E-MAIL", "X-RAYS", "T-SHIRT", "U-HAUL", "V-NECK", "CD-ROM", "WI-FI", "HI-FI", "E-BOOK", "A-LIST", "B-LIST"]
    potential_tails = list(set([t for t in potential_tails if len(t) >= 4 and t not in false_positives]))
    
    if not potential_tails:
        return None
        
    print(f"Immatriculations potentielles trouvées pour {vip_name}: {potential_tails}")
    
    # 3. Vérification dans aircraftDatabase.csv
    csv_path = os.path.join(os.path.dirname(__file__), "aircraftDatabase.csv")
    if not os.path.exists(csv_path):
        print("aircraftDatabase.csv introuvable.")
        return None
        
    # Normaliser la recherche (sans tiret pour la comparaison)
    search_tails = {t: t.replace("-", "") for t in potential_tails}
    
    found_jets = []
    try:
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                reg = row.get('registration', '').upper()
                reg_no_dash = reg.replace('-', '')
                
                # Check against our potential tails
                for original_tail, search_tail in search_tails.items():
                    if reg == original_tail or reg_no_dash == search_tail:
                        icao24 = row.get('icao24', '').lower()
                        if icao24:
                            found_jets.append({
                                "icao24": icao24,
                                "tail_number": reg,
                                "description": f"{row.get('manufacturername', '')} {row.get('model', '')} ({row.get('operator', '') or row.get('owner', 'Privé')})".strip()
                            })
    except Exception as e:
        print(f"Erreur de lecture CSV: {e}")
        return None
        
    if found_jets:
        # On prend le premier jet trouvé (le plus probable)
        return found_jets[0]
        
    return None

if __name__ == "__main__":
    # Test
    import sys
    name = "Elon Musk"
    if len(sys.argv) > 1:
        name = sys.argv[1]
    res = find_vip_jet(name)
    print(f"Résultat pour {name}: {res}")

