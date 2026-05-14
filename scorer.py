import json
import os
import unicodedata
from typing import Dict, Optional, Any
from sqlalchemy.orm import Session
from models import Flight

from utils import normaliser


def score_president(pays: str, db: Session) -> Optional[Dict[str, Any]]:
    """
    Calcule le score de transparence et les métriques d'utilisation pour la flotte 
    d'un pays donné, en se basant sur les vols enregistrés en base.
    """
    # 1. Charger la base de connaissances JSON
    json_path = os.path.join(os.path.dirname(__file__), "data", "jets_africains.json")
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            flottes = json.load(f)
    except Exception as e:
        print(f"Erreur lors du chargement de {json_path}: {e}")
        return None

    # 2. Trouver la flotte du pays
    pays_data = None
    for item in flottes:
        if normaliser(item["pays"]) == normaliser(pays):
            pays_data = item
            break
            
    if not pays_data:
        print(f"Pays '{pays}' non trouvé dans la base de données JSON.")
        return None
        
    icao24_list = []
    conso_par_icao24 = {}
    tail_par_icao24 = {}
    for jet in pays_data.get("flotte", []):
        icao24 = jet.get("icao24")
        if icao24:
            icao24_list.append(icao24.lower())
            # On stocke la consommation spécifique (par défaut 3500 si absente)
            conso_par_icao24[icao24.lower()] = jet.get("consommation_kg_par_heure") or 3500
            tail_par_icao24[icao24.lower()] = jet.get("tail_number") or "Inconnu"

    if not icao24_list:
        return None

    # 3. Récupérer tous les vols de ces jets depuis le début du mois (Reset mensuel)
    import datetime
    now = datetime.datetime.now()
    start_of_month = datetime.datetime(now.year, now.month, 1)
    start_unix = int(start_of_month.timestamp())

    vols = db.query(Flight).filter(
        Flight.icao24.in_(icao24_list),
        Flight.departure_time >= start_unix
    ).all()
    
    if not vols:
        return None

    # 4. Calculer les métriques
    total_heures = 0.0
    total_vols = len(vols)
    vols_suspects = 0
    vols_avec_aeroports = 0
    co2_total_kg = 0.0
    vols_icao24_utilises = set()
    
    # Coût horaire estimé en USD (moyenne pour jet privé)
    COUT_HORAIRE_USD = 10000 

    for vol in vols:
        vols_icao24_utilises.add(vol.icao24.lower())
        # Heures de vol
        duree_h = (vol.duration_minutes or 0) / 60.0
        total_heures += duree_h
        
        # CO2 : consommation horaire * heures de vol * 3.16 kg CO2 par kg de kérosène
        conso_horaire = conso_par_icao24.get(vol.icao24.lower(), 3500)
        co2_total_kg += (duree_h * conso_horaire * 3.16)
        
        # Classification
        if vol.classification == "personnel":
            vols_suspects += 1
            
        # Qualité des données (taux ADS-B)
        if vol.departure_airport and vol.arrival_airport:
            vols_avec_aeroports += 1

    ratio_suspects = vols_suspects / total_vols if total_vols > 0 else 0.0
    taux_ads_b = vols_avec_aeroports / total_vols if total_vols > 0 else 0.0
    cout_usd = total_heures * COUT_HORAIRE_USD

    jets_utilises = [tail_par_icao24.get(i) for i in vols_icao24_utilises if tail_par_icao24.get(i)]

    # 5. Calcul du score global de 0 à 100 (plus élevé = plus suspect/opaque)
    # Pondérations: 
    # Ratio suspect: 40%
    # Opacité ADS-B (1 - taux): 30%
    # Volume total vols (pénalise l'abus): 20% (max à 50 vols)
    # Volume heures (pénalise l'abus): 10% (max à 200 heures)
    score_suspect = ratio_suspects * 40
    score_opacite = (1 - taux_ads_b) * 30
    score_volume = min(total_vols / 50.0, 1.0) * 20
    score_heures = min(total_heures / 200.0, 1.0) * 10
    
    score_global = round(score_suspect + score_opacite + score_volume + score_heures, 2)

    # 6. Niveau d'alerte
    if score_global > 70:
        niveau = "🔴 CRITIQUE"
    elif score_global >= 50:
        niveau = "🟠 ÉLEVÉ"
    elif score_global >= 30:
        niveau = "🟡 MODÉRÉ"
    else:
        niveau = "🟢 NORMAL"

    vols_personnels = vols_suspects
    vols_officiels = total_vols - vols_personnels

    return {
        "pays": pays_data["pays"],
        "dirigeant": pays_data["dirigeant"],
        "niveau": niveau,
        "total_heures": round(total_heures, 2),
        "total_vols": total_vols,
        "vols_officiels": vols_officiels,
        "vols_personnels": vols_personnels,
        "co2_kg": round(co2_total_kg, 2),
        "cout_usd": round(cout_usd, 2),
        "ratio_suspects": round(ratio_suspects, 4),
        "taux_ads_b": round(taux_ads_b, 4),
        "score_global": score_global,
        "jets_utilises": jets_utilises
    }
