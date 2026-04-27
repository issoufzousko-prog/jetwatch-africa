import os
import json
import time
import requests
from datetime import datetime
from sqlalchemy.orm import Session
from models import Flight

POLL_LOG_FILE = os.path.join(os.path.dirname(__file__), "poll.log")

def log_poll(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}\n"
    with open(POLL_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)

def get_live_position(icao24: str) -> dict | None:
    """
    Interroge l'API gratuite ADSBExchange via adsb.lol pour obtenir la position en direct d'un aéronef.
    Retourne les données si l'avion est détecté, sinon None.
    """
    url = f"https://api.adsb.lol/v2/hex/{icao24}"
    headers = {"Accept": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "ac" in data and len(data["ac"]) > 0:
                return data["ac"][0]
    except Exception as e:
        pass # evite le spam dans la console
    return None

def poll_all_fleet(db: Session) -> dict:
    """
    Parcourt l'ensemble de la flotte présidentielle africaine, vérifie 
    le statut en vol via ADSBExchange et met à jour la base SQLite.
    """
    stats = {"detectes": 0, "en_vol": 0, "atterris": 0}
    json_path = os.path.join(os.path.dirname(__file__), "data", "jets_africains.json")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            flottes = json.load(f)
    except Exception:
        return stats

    now = int(time.time())

    for item in flottes:
        for jet in item.get("flotte", []):
            icao24 = jet.get("icao24")
            if not icao24:
                continue

            tail = jet.get("tail_number", "Inconnu")
            
            # Protection contre le rate limit de adsb.lol
            time.sleep(2)

            live_data = get_live_position(icao24)
            if live_data:
                stats["detectes"] += 1
                is_airborne = not live_data.get("GND", True) # GND = True si au sol
                callsign = str(live_data.get("flight", "")).strip() or "Inconnu"
                
                # Chercher un vol ouvert (departure_time défini mais arrival_time null)
                vol_ouvert = db.query(Flight).filter(
                    Flight.icao24 == icao24,
                    Flight.arrival_time == None
                ).order_by(Flight.departure_time.desc()).first()

                if is_airborne:
                    stats["en_vol"] += 1
                    if not vol_ouvert:
                        # Créer un nouveau vol
                        new_flight = Flight(
                            icao24=icao24,
                            callsign=callsign,
                            departure_airport=None, # On ne connait pas l'origine exacte en direct sans recoupement
                            arrival_airport=None,
                            departure_time=now,
                            arrival_time=None,
                            duration_minutes=0,
                            classification=None,
                            co2_kg=None
                        )
                        db.add(new_flight)
                        log_poll(f"✈ {tail} détecté EN VOL (Nouveau vol) | callsign: {callsign} | durée: 0 min")
                    else:
                        # Mettre à jour la durée
                        vol_ouvert.duration_minutes = round((now - vol_ouvert.departure_time) / 60.0, 2)
                        log_poll(f"✈ {tail} détecté EN VOL | callsign: {callsign} | durée: {vol_ouvert.duration_minutes} min")
                        
                else:
                    # L'avion est au sol
                    if vol_ouvert:
                        # Fermer le vol
                        vol_ouvert.arrival_time = now
                        vol_ouvert.duration_minutes = round((now - vol_ouvert.departure_time) / 60.0, 2)
                        stats["atterris"] += 1
                        log_poll(f"✈ {tail} détecté AU SOL (Vol terminé) | callsign: {callsign} | durée totale: {vol_ouvert.duration_minutes} min")
                    else:
                        log_poll(f"✈ {tail} détecté AU SOL | callsign: {callsign} | en stationnement")
                        
    db.commit()
    return stats
