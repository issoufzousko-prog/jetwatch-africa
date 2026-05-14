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
    Optimisation Vercel : Utilise les données globales pour mettre à jour toute la flotte
    en une seule requête au lieu de boucler avec des sleep(1.5s).
    """
    stats = {"detectes": 0, "en_vol": 0, "atterris": 0, "sources": {}}
    now = int(time.time())
    
    # 1. Récupérer les données globales (tous les avions d'un coup)
    all_aircraft = []
    for provider in ADSB_PROVIDERS:
        url = provider["base_url"] + provider["all_endpoint"]
        try:
            resp = requests.get(url, headers={"Accept": "application/json"}, timeout=15)
            if resp.status_code == 200:
                all_aircraft = resp.json().get("ac", [])
                stats["sources"][provider["name"]] = len(all_aircraft)
                if all_aircraft:
                    break # On prend le premier qui répond
        except Exception:
            continue

    # 2. Créer un index ICAO24 -> Data
    ac_index = {ac.get("hex", "").lower(): ac for ac in all_aircraft if ac.get("hex")}

    # 3. Récupérer la flotte cible
    target_fleets = db.query(TargetFleet).all()
    known_icao24s = {f.icao24.lower() for f in target_fleets if f.icao24}

    # 4. Détecter les vols fantômes (déjà optimisé dans scan_ghost_fleet)
    scan_ghost_fleet(db, known_icao24s)

    # 5. Mettre à jour la flotte connue à partir de l'index
    for fleet in target_fleets:
        icao24 = (fleet.icao24 or "").lower()
        if not icao24:
            continue

        live_data = ac_index.get(icao24)
        vol_ouvert = db.query(Flight).filter(Flight.icao24 == icao24, Flight.arrival_time == None).first()

        if live_data:
            stats["detectes"] += 1
            is_airborne = determine_airborne(live_data)
            callsign = str(live_data.get("flight", "")).strip() or "Inconnu"
            lat, lon = live_data.get("lat"), live_data.get("lon")
            alt = live_data.get("alt_baro") if isinstance(live_data.get("alt_baro"), (int, float)) else None

            if is_airborne:
                stats["en_vol"] += 1
                if not vol_ouvert:
                    vol_ouvert = Flight(icao24=icao24, callsign=callsign, departure_time=now, duration_minutes=0)
                    db.add(vol_ouvert)
                    db.flush()
                
                vol_ouvert.duration_minutes = round((now - vol_ouvert.departure_time) / 60.0, 2)
                if lat is not None and lon is not None:
                    vol_ouvert.positions.append(FlightPosition(lat=lat, lon=lon, alt_baro=alt, gs=live_data.get("gs"), track=live_data.get("track"), timestamp=now))
            else:
                if vol_ouvert:
                    vol_ouvert.arrival_time = now
                    vol_ouvert.duration_minutes = round((now - vol_ouvert.departure_time) / 60.0, 2)
                    stats["atterris"] += 1
                    db.commit()
        else:
            # Hors radar : Fermeture auto après 1h
            if vol_ouvert:
                last_pos = max([p.timestamp for p in vol_ouvert.positions] + [vol_ouvert.departure_time])
                if (now - last_pos) > 3600:
                    vol_ouvert.arrival_time = last_pos
                    vol_ouvert.duration_minutes = round((last_pos - vol_ouvert.departure_time) / 60.0, 2)
                    stats["atterris"] += 1

    db.commit()
    return stats
