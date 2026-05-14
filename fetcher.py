import os
import json
import time
import requests
from datetime import datetime
from sqlalchemy.orm import Session
from models import Flight, FlightPosition, TargetFleet

POLL_LOG_FILE = os.path.join(os.path.dirname(__file__), "poll.log")

def log_poll(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}\n"
    with open(POLL_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)


# ─────────────────────────────────────────────────────────────────────
# PROVIDERS ADS-B — Multi-source avec fallback automatique
# ─────────────────────────────────────────────────────────────────────

# Configuration des deux providers conformes aux guides officiels
ADSB_PROVIDERS = [
    {
        "name": "adsb.lol",
        "base_url": "https://api.adsb.lol",
        "icao_endpoint": "/v2/icao/{icao}",        # Guide: GET /v2/icao/{icao}
        "callsign_endpoint": "/v2/callsign/{cs}",  # Guide: GET /v2/callsign/{callsign}
        "area_endpoint": "/v2/lat/{lat}/lon/{lon}/dist/{dist}",  # Guide: GET /v2/lat/.../lon/.../dist/...
        "all_endpoint": "/v2/all",  # Guide: GET /v2/all (Tous les avions)
        "timeout": 15,
    },
    {
        "name": "adsb.fi",
        "base_url": "https://opendata.adsb.fi/api",
        "icao_endpoint": "/v2/hex/{icao}",          # Guide: GET /v2/hex/{hex}
        "callsign_endpoint": "/v2/callsign/{cs}",   # Guide: GET /v2/callsign/{callsign}
        "area_endpoint": "/v3/lat/{lat}/lon/{lon}/dist/{dist}",  # Guide: GET /v3/lat/.../lon/.../dist/...
        "all_endpoint": "/v2/all", # Compatible avec adsb.lol
        "timeout": 15,
    },
]


def _query_provider(provider: dict, endpoint_template: str, **kwargs) -> dict | None:
    """
    Interroge un provider ADS-B spécifique.
    Retourne les données brutes de l'avion si trouvé, sinon None.
    """
    url = provider["base_url"] + endpoint_template.format(**kwargs)
    headers = {"Accept": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=provider["timeout"])
        if response.status_code == 200:
            data = response.json()
            # Les deux APIs utilisent le même format de réponse : { "ac": [...] }
            if "ac" in data and len(data["ac"]) > 0:
                return data["ac"][0]
    except Exception:
        pass  # Silencieux — le fallback prendra le relais
    return None


def get_live_position(icao24: str) -> dict | None:
    """
    Interroge les APIs ADS-B (adsb.lol puis adsb.fi en fallback) pour
    obtenir la position en direct d'un aéronef par son code ICAO24.

    Stratégie : essaie chaque provider dans l'ordre. Si le premier
    ne retourne rien (timeout, erreur, avion absent), passe au suivant.
    """
    for provider in ADSB_PROVIDERS:
        result = _query_provider(
            provider,
            provider["icao_endpoint"],
            icao=icao24
        )
        if result is not None:
            return result
    return None


def get_area_aircraft(lat: float, lon: float, dist_nm: int) -> list:
    """
    Interroge les APIs ADS-B pour obtenir tous les avions dans un rayon
    autour d'un point géographique (en nautical miles).

    Stratégie : essaie chaque provider. Retourne la première réponse
    non-vide. En cas d'échec total, retourne une liste vide.
    """
    headers = {"Accept": "application/json"}
    for provider in ADSB_PROVIDERS:
        url = provider["base_url"] + provider["area_endpoint"].format(
            lat=lat, lon=lon, dist=dist_nm
        )
        try:
            response = requests.get(url, headers=headers, timeout=provider["timeout"])
            if response.status_code == 200:
                data = response.json()
                aircraft = data.get("ac", [])
                if aircraft:
                    return aircraft
        except Exception:
            pass
    return []


# ─────────────────────────────────────────────────────────────────────
# LOGIQUE DE DÉTECTION — is_airborne robuste
# ─────────────────────────────────────────────────────────────────────

def determine_airborne(ac_data: dict) -> bool:
    """
    Détermine si un aéronef est en vol ou au sol, en gérant correctement
    tous les cas de l'API ADS-B :

    1. Champ "GND" (bool) — le plus fiable quand il est présent.
       GND=True  → au sol,  GND=False → en vol.

    2. alt_baro = "ground" (string) — l'API renvoie parfois la string
       "ground" au lieu d'un nombre quand l'avion est au sol.

    3. Fallback alt_baro / gs — si ni GND ni "ground", on vérifie
       si on a une altitude barométrique numérique > 0 ou une vitesse > 50 kt.
       Un avion au sol peut avoir gs > 0 (taxi), donc seuil de 50 kt.
    """
    # Priorité 1 : champ GND explicite (le plus fiable)
    if "GND" in ac_data:
        gnd_val = ac_data["GND"]
        # Certaines implémentations renvoient un string "true"/"false"
        if isinstance(gnd_val, str):
            return gnd_val.lower() != "true"
        return not gnd_val

    # Priorité 2 : alt_baro = "ground" (string spéciale de l'API)
    alt_baro = ac_data.get("alt_baro")
    if isinstance(alt_baro, str) and alt_baro.lower() == "ground":
        return False  # Au sol

    # Priorité 3 : altitude numérique ou vitesse significative
    gs = ac_data.get("gs")

    # Si aucune donnée d'altitude ni de vitesse, considérer au sol
    if alt_baro is None and gs is None:
        return False

    # Si on a une altitude numérique > 0, c'est en vol
    if isinstance(alt_baro, (int, float)) and alt_baro > 0:
        return True

    # Si on a une vitesse significative (> 50 kt exclut le taxi)
    if isinstance(gs, (int, float)) and gs > 50:
        return True

    # Par défaut, si on a des données mais pas suffisantes, au sol
    return False


# ─────────────────────────────────────────────────────────────────────
# GEOFENCING — Flotte Fantôme
# ─────────────────────────────────────────────────────────────────────

CAPITALS_GEOFENCE = [
    {"name": "Yaoundé", "pays": "Cameroun", "lat": 3.722, "lon": 11.523}, # Nsimalen
    {"name": "Libreville", "pays": "Gabon", "lat": 0.458, "lon": 9.412}, # Léon Mba
    {"name": "Malabo", "pays": "Guinée équatoriale", "lat": 3.755, "lon": 8.708}, # Malabo Intl
    {"name": "Brazzaville", "pays": "Congo", "lat": -4.251, "lon": 15.253}, # Maya-Maya
    {"name": "Dakar", "pays": "Sénégal", "lat": 14.670, "lon": -17.073}, # DSS
    {"name": "Lomé", "pays": "Togo", "lat": 6.165, "lon": 1.254} # Gnassingbé Eyadéma
]

LUXURY_JET_TYPES = ["GLF5", "GLF6", "FA7X", "FA8X", "GLEX", "GL5T", "F2TH", "CL60"]

def scan_ghost_fleet(db: Session, known_icao24s: set) -> None:
    """
    Scanne l'espace aérien autour des capitales pour détecter des jets de luxe
    (Flotte Fantôme) qui ne sont pas dans la liste officielle.
    Utilise le multi-provider (adsb.lol + adsb.fi) pour la couverture maximale.
    """
    now = int(time.time())
    for capital in CAPITALS_GEOFENCE:
        # Rate limit protection
        time.sleep(1.5)

        # Utilise le multi-provider pour le scan de zone (radius 25 NM)
        aircraft_list = get_area_aircraft(capital["lat"], capital["lon"], 25)

        for ac in aircraft_list:
            icao24 = ac.get("hex", "").lower()
            if not icao24 or icao24 in known_icao24s:
                continue
            
            ac_type = ac.get("t", "INCONNU")
            # Si c'est un jet de luxe et qu'il est en vol
            if ac_type in LUXURY_JET_TYPES:
                # Utilise la nouvelle logique robuste
                if determine_airborne(ac):
                    # Vérifier si ce vol fantôme est déjà suivi
                    vol_ouvert = db.query(Flight).filter(Flight.icao24 == icao24, Flight.arrival_time == None).first()
                    if not vol_ouvert:
                        log_poll(f"🚨 VOL FANTÔME DÉTECTÉ depuis {capital['name']}: {icao24} ({ac_type})")
                        callsign = str(ac.get("flight", "")).strip() or "Location Privée"
                        vol_ouvert = Flight(
                            icao24=icao24,
                            callsign=callsign,
                            departure_time=now,
                            duration_minutes=0
                        )
                        db.add(vol_ouvert)
                        db.flush()  # FIX: Rendre le vol visible immédiatement pour éviter les doublons
                    
                    # Mettre à jour sa position
                    lat = ac.get("lat")
                    lon = ac.get("lon")
                    if lat is not None and lon is not None:
                        alt_raw = ac.get("alt_baro")
                        # Nettoyer alt_baro si c'est "ground"
                        alt_val = alt_raw if isinstance(alt_raw, (int, float)) else None
                        new_pos = FlightPosition(
                            lat=lat,
                            lon=lon,
                            alt_baro=alt_val,
                            gs=ac.get("gs"),
                            track=ac.get("track"),
                            timestamp=now
                        )
                        vol_ouvert.positions.append(new_pos)
                    db.commit()


def scan_global_ghost_fleet(db: Session, known_icao24s: set) -> None:
    """
    Scanne TOUT l'espace aérien via /v2/all pour détecter des jets de luxe
    suspects n'importe où en Afrique (ou ailleurs) qui ne sont pas dans la base.
    Conforme au guide: inclure /v2/all dans la détection.
    """
    now = int(time.time())
    headers = {"Accept": "application/json"}
    
    # On essaie le premier provider qui supporte /all
    for provider in ADSB_PROVIDERS:
        if "all_endpoint" not in provider:
            continue
            
        url = provider["base_url"] + provider["all_endpoint"]
        try:
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code == 200:
                data = response.json()
                aircraft_list = data.get("ac", [])
                
                detected_count = 0
                for ac in aircraft_list:
                    icao24 = ac.get("hex", "").lower()
                    if not icao24 or icao24 in known_icao24s:
                        continue
                    
                    # On filtre sur les jets de luxe pour éviter de polluer avec des avions commerciaux
                    ac_type = ac.get("t", "")
                    if ac_type in LUXURY_JET_TYPES:
                        # On vérifie si l'avion est au-dessus de l'Afrique (approximatif)
                        lat = ac.get("lat")
                        lon = ac.get("lon")
                        if lat is not None and lon is not None:
                            # Rectangle englobant l'Afrique : Lat [-35, 37], Lon [-20, 52]
                            if -35 <= lat <= 37 and -20 <= lon <= 52:
                                if determine_airborne(ac):
                                    # Détection Vol Fantôme Global
                                    vol_ouvert = db.query(Flight).filter(Flight.icao24 == icao24, Flight.arrival_time == None).first()
                                    if not vol_ouvert:
                                        log_poll(f"🌍 VOL FANTÔME GLOBAL détecté: {icao24} ({ac_type}) à Lat:{lat}, Lon:{lon}")
                                        callsign = str(ac.get("flight", "")).strip() or "Suspect"
                                        vol_ouvert = Flight(
                                            icao24=icao24,
                                            callsign=callsign,
                                            departure_time=now,
                                            duration_minutes=0
                                        )
                                        db.add(vol_ouvert)
                                        db.flush()
                                    
                                    # Mise à jour position
                                    new_pos = FlightPosition(
                                        lat=lat,
                                        lon=lon,
                                        alt_baro=ac.get("alt_baro") if isinstance(ac.get("alt_baro"), (int, float)) else None,
                                        gs=ac.get("gs"),
                                        track=ac.get("track"),
                                        timestamp=now
                                    )
                                    vol_ouvert.positions.append(new_pos)
                                    detected_count += 1
                
                if detected_count > 0:
                    db.commit()
                return # Succès avec ce provider
        except Exception as e:
            print(f"Erreur scan_global: {e}")
            continue


# ─────────────────────────────────────────────────────────────────────
# POLLING PRINCIPAL — Boucle de détection de la flotte
# ─────────────────────────────────────────────────────────────────────

def poll_all_fleet(db: Session) -> dict:
    """
    Parcourt l'ensemble de la flotte présidentielle africaine, vérifie 
    le statut en vol via les APIs ADS-B (adsb.lol + adsb.fi) et met à jour
    la base SQLite avec les positions GPS.

    Corrections appliquées :
    - Multi-provider (adsb.lol → adsb.fi fallback)
    - Logique is_airborne robuste (gère alt_baro="ground")
    - db.flush() après création de vol pour éviter les doublons
    - Nettoyage de alt_baro avant insertion en base
    """
    stats = {"detectes": 0, "en_vol": 0, "atterris": 0, "sources": {"adsb.lol": 0, "adsb.fi": 0}}
    target_fleets = db.query(TargetFleet).all()
    now = int(time.time())

    known_icao24s = set()
    for fleet in target_fleets:
        if fleet.icao24:
            known_icao24s.add(fleet.icao24.lower())
                
    # Lancer le Geofencing pour les flottes fantômes (Près des capitales)
    scan_ghost_fleet(db, known_icao24s)
    
    # Lancer le Scan Global (Partout en Afrique via /v2/all)
    scan_global_ghost_fleet(db, known_icao24s)

    for fleet in target_fleets:
        icao24 = fleet.icao24
        if not icao24:
            continue

        tail = fleet.tail_number or "Inconnu"
            
        # Protection contre le rate limit (1.5s entre chaque requête)
        time.sleep(1.5)

        live_data = get_live_position(icao24)
        if live_data:
            stats["detectes"] += 1
            
            # Utilise la nouvelle logique robuste pour déterminer si l'avion est en vol
            is_airborne = determine_airborne(live_data)
                
            callsign = str(live_data.get("flight", "")).strip() or "Inconnu"
            
            # Extraire les coordonnées
            lat = live_data.get("lat")
            lon = live_data.get("lon")
            alt_baro_raw = live_data.get("alt_baro")
            gs = live_data.get("gs")
            track = live_data.get("track")

            # Nettoyer alt_baro : si c'est la string "ground", stocker None
            alt_baro = alt_baro_raw if isinstance(alt_baro_raw, (int, float)) else None
            
            # Chercher un vol ouvert (departure_time défini mais arrival_time null)
            vol_ouvert = db.query(Flight).filter(
                Flight.icao24 == icao24,
                Flight.arrival_time == None
            ).order_by(Flight.departure_time.desc()).first()

            if is_airborne:
                stats["en_vol"] += 1
                if not vol_ouvert:
                    # Créer un nouveau vol
                    vol_ouvert = Flight(
                        icao24=icao24,
                        callsign=callsign,
                        departure_airport=None,
                        arrival_airport=None,
                        departure_time=now,
                        arrival_time=None,
                        duration_minutes=0,
                        classification=None,
                        co2_kg=None
                    )
                    db.add(vol_ouvert)
                    db.flush()  # FIX: Rendre le vol visible immédiatement pour éviter les doublons
                    log_poll(f"✈ {tail} détecté EN VOL (Nouveau vol) | callsign: {callsign}")
                else:
                    # Mettre à jour la durée
                    vol_ouvert.duration_minutes = round((now - vol_ouvert.departure_time) / 60.0, 2)
                    log_poll(f"✈ {tail} détecté EN VOL | callsign: {callsign} | durée: {vol_ouvert.duration_minutes} min")
                    
                # Enregistrer la position GPS si disponible
                if lat is not None and lon is not None:
                    new_pos = FlightPosition(
                        lat=lat,
                        lon=lon,
                        alt_baro=alt_baro,
                        gs=gs,
                        track=track,
                        timestamp=now
                    )
                    vol_ouvert.positions.append(new_pos)
                    
            else:
                # L'avion est au sol
                if vol_ouvert:
                    # Fermer le vol
                    vol_ouvert.arrival_time = now
                    vol_ouvert.duration_minutes = round((now - vol_ouvert.departure_time) / 60.0, 2)
                    stats["atterris"] += 1
                    
                    # Dernière position au sol si dispo
                    if lat is not None and lon is not None:
                        new_pos = FlightPosition(
                            lat=lat,
                            lon=lon,
                            alt_baro=alt_baro,
                            gs=gs,
                            track=track,
                            timestamp=now
                        )
                        vol_ouvert.positions.append(new_pos)
                        
                    log_poll(f"✈ {tail} détecté AU SOL (Vol terminé) | callsign: {callsign} | durée totale: {vol_ouvert.duration_minutes} min")
                else:
                    pass # Avion parqué, rien à faire
        else:
            # L'avion n'est plus détecté du tout par les APIs (Hors radar ou transpondeur éteint)
            vol_ouvert = db.query(Flight).filter(
                Flight.icao24 == icao24,
                Flight.arrival_time == None
            ).order_by(Flight.departure_time.desc()).first()

            if vol_ouvert:
                # Vérifier depuis combien de temps on a perdu le signal
                last_update = vol_ouvert.departure_time
                if vol_ouvert.positions:
                    # Les positions sont ordonnées par l'insertion, la dernière est à la fin
                    last_update = max([p.timestamp for p in vol_ouvert.positions] + [vol_ouvert.departure_time])
                
                # Si on n'a plus de signal depuis plus de 60 minutes (3600 secondes), on ferme le vol
                if (now - last_update) > 3600:
                    vol_ouvert.arrival_time = last_update
                    vol_ouvert.duration_minutes = round((last_update - vol_ouvert.departure_time) / 60.0, 2)
                    stats["atterris"] += 1
                    log_poll(f"✈ {tail} perdu du radar. Fermeture auto (signal perdu depuis >1h). Durée: {vol_ouvert.duration_minutes} min")

    db.commit()
    return stats
