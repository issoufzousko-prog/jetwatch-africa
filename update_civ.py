import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "jets_africains.json")

def update_ivory_coast():
    with open(DB_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    for item in data:
        if "ivoire" in item["pays"].lower():
            item["flotte"] = [
                {
                    "icao24": "038613",
                    "tail_number": "TU-VAS",
                    "modele": "Airbus A319-133 ACJ",
                    "usage": "présidentiel",
                    "autonomie_km": 11100,
                    "consommation_kg_par_heure": 2400,
                    "source": "User Correction",
                    "verifie": True
                },
                {
                    "icao24": "038615",
                    "tail_number": "TU-VAE",
                    "modele": "Gulfstream G550",
                    "usage": "gouvernemental",
                    "autonomie_km": 12500,
                    "consommation_kg_par_heure": 1100,
                    "source": "User Correction",
                    "verifie": True
                },
                {
                    "icao24": "707505",
                    "tail_number": "TU-VAG",
                    "modele": "Gulfstream G450",
                    "usage": "gouvernemental",
                    "autonomie_km": 8000,
                    "consommation_kg_par_heure": 1100,
                    "source": "User Correction",
                    "verifie": True
                }
            ]
            break
            
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        print("Mise à jour réussie de la flotte ivoirienne.")

if __name__ == "__main__":
    update_ivory_coast()
