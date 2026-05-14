"""
JetWatch Africa -- Script de diagnostic ADS-B
=============================================
Ce script verifie l'algorithme de detection de vols en interrogeant l'API adsb.lol
pour chaque avion de la flotte, et produit un rapport detaille.
"""

import os
import sys
import json
import time
import io
import requests
from datetime import datetime

# Force UTF-8 on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
FLEET_PATH = os.path.join(DATA_DIR, "jets_africains.json")

def load_fleet():
    with open(FLEET_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def query_adsb(icao24: str) -> dict | None:
    url = f"https://api.adsb.lol/v2/hex/{icao24}"
    headers = {"Accept": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if "ac" in data and len(data["ac"]) > 0:
                return data["ac"][0]
            return {"_empty": True, "_status": "no_aircraft_in_response"}
        return {"_error": True, "_status_code": response.status_code}
    except Exception as e:
        return {"_exception": True, "_error": str(e)}

def analyze_airborne_logic(ac_data: dict) -> dict:
    """Reproduit exactement la logique is_airborne de fetcher.py"""
    result = {
        "has_GND_field": "GND" in ac_data,
        "GND_value": ac_data.get("GND"),
        "alt_baro": ac_data.get("alt_baro"),
        "alt_baro_type": type(ac_data.get("alt_baro")).__name__,
        "gs": ac_data.get("gs"),
        "lat": ac_data.get("lat"),
        "lon": ac_data.get("lon"),
        "track": ac_data.get("track"),
        "flight": ac_data.get("flight"),
    }
    
    is_airborne = True
    logic_path = ""
    
    if "GND" in ac_data:
        gnd_val = ac_data.get("GND", True)
        if isinstance(gnd_val, str):
            is_airborne = gnd_val.lower() != "true"
            logic_path = f"GND field (string): '{gnd_val}' -> airborne={is_airborne}"
        else:
            is_airborne = not gnd_val
            logic_path = f"GND field (bool): {gnd_val} -> airborne={is_airborne}"
    elif ac_data.get("alt_baro") is None and ac_data.get("gs") is None:
        is_airborne = False
        logic_path = "No GND, no alt_baro, no gs -> grounded"
    else:
        alt_val = ac_data.get("alt_baro")
        if isinstance(alt_val, str) and alt_val.lower() == "ground":
            # BUG CRITIQUE: fetcher.py traite alt_baro="ground" comme en vol
            # car "ground" is not None => True
            is_airborne = False  # Corrige pour le diagnostic
            logic_path = f"alt_baro='ground' (BUG: fetcher.py dit EN VOL car alt_baro is not None)"
            result["BUG_DETECTED"] = "alt_baro='ground' est traite comme en vol par l'algo actuel!"
        else:
            logic_path = f"alt_baro={alt_val}, gs={ac_data.get('gs')} -> airborne=True"
    
    result["is_airborne"] = is_airborne
    result["logic_path"] = logic_path
    
    return result

def run_diagnostic():
    fleet = load_fleet()
    
    print("=" * 80)
    print("  JETWATCH AFRICA -- DIAGNOSTIC COMPLET DE DETECTION ADS-B")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    total_jets = 0
    jets_with_icao = 0
    jets_no_icao = 0
    jets_detected = 0
    jets_airborne = 0
    jets_on_ground = 0
    jets_not_detected = 0
    bugs_found = []
    duplicate_icao = {}
    results = []
    
    # Phase 1: Audit de la flotte
    print("\n[PHASE 1] AUDIT DE LA BASE DE DONNEES FLOTTE")
    print("-" * 60)
    
    all_icao24s = []
    for entry in fleet:
        pays = entry.get("pays", "?")
        dirigeant = entry.get("dirigeant", "?")
        for jet in entry.get("flotte", []):
            total_jets += 1
            icao = jet.get("icao24")
            tail = jet.get("tail_number") or (jet.get("description", "?")[:30] if jet.get("description") else "?")
            
            if not icao:
                jets_no_icao += 1
                results.append({
                    "pays": pays, "dirigeant": dirigeant, "tail": tail,
                    "icao24": None, "status": "NO_ICAO24",
                    "issue": "Impossible a tracker sans code ICAO24"
                })
                continue
            
            icao_lower = icao.lower()
            jets_with_icao += 1
            
            if icao_lower in duplicate_icao:
                duplicate_icao[icao_lower].append(f"{pays}/{tail}")
                bugs_found.append(f"DOUBLON ICAO24: {icao_lower} utilise par {duplicate_icao[icao_lower]}")
            else:
                duplicate_icao[icao_lower] = [f"{pays}/{tail}"]
            
            all_icao24s.append({
                "pays": pays, "dirigeant": dirigeant,
                "tail": tail, "icao24": icao_lower
            })
    
    print(f"  Total avions en base     : {total_jets}")
    print(f"  Avec code ICAO24 valide  : {jets_with_icao}")
    print(f"  Sans ICAO24 (non-trackables): {jets_no_icao}")
    
    dupes = {k: v for k, v in duplicate_icao.items() if len(v) > 1}
    if dupes:
        print(f"\n  [WARNING] DOUBLONS ICAO24 TROUVES ({len(dupes)}):")
        for icao, owners in dupes.items():
            print(f"     {icao} -> {', '.join(owners)}")
            bugs_found.append(f"Doublon ICAO: {icao} ({', '.join(owners)})")
    
    # Phase 2: Interrogation API
    print(f"\n[PHASE 2] INTERROGATION API ADS-B ({len(all_icao24s)} avions)")
    print("-" * 60)
    
    for i, jet_info in enumerate(all_icao24s):
        icao = jet_info["icao24"]
        pays = jet_info["pays"]
        tail = jet_info["tail"]
        
        if i > 0:
            time.sleep(1.5)
        
        print(f"  [{i+1}/{len(all_icao24s)}] {tail} ({icao}) -- {pays}...", end=" ", flush=True)
        
        ac_data = query_adsb(icao)
        
        if ac_data is None:
            jets_not_detected += 1
            print("[X] Pas de reponse")
            results.append({**jet_info, "status": "NO_RESPONSE", "api_data": None})
            continue
        
        if ac_data.get("_empty"):
            jets_not_detected += 1
            print("[ ] Hors radar (transpondeur off)")
            results.append({**jet_info, "status": "OFFLINE", "api_data": ac_data})
            continue
        
        if ac_data.get("_error"):
            jets_not_detected += 1
            print(f"[ERR] HTTP {ac_data.get('_status_code')}")
            results.append({**jet_info, "status": "HTTP_ERROR", "api_data": ac_data})
            continue
        
        if ac_data.get("_exception"):
            jets_not_detected += 1
            print(f"[EXC] {ac_data.get('_error')}")
            results.append({**jet_info, "status": "EXCEPTION", "api_data": ac_data})
            continue
        
        jets_detected += 1
        analysis = analyze_airborne_logic(ac_data)
        
        if analysis["is_airborne"]:
            jets_airborne += 1
            print(f"[FLY] EN VOL | alt={analysis['alt_baro']} | gs={analysis['gs']} | {analysis['logic_path']}")
        else:
            jets_on_ground += 1
            print(f"[GND] AU SOL | {analysis['logic_path']}")
        
        if "BUG_DETECTED" in analysis:
            bugs_found.append(f"{tail} ({icao}): {analysis['BUG_DETECTED']}")
            print(f"     [BUG] {analysis['BUG_DETECTED']}")
        
        results.append({**jet_info, "status": "DETECTED", "analysis": analysis, 
                        "raw_fields": {k: ac_data.get(k) for k in ["hex", "flight", "alt_baro", "alt_geom", "gs", "track", "lat", "lon", "GND", "t", "r"]}})
    
    # Phase 3: Analyse des bugs dans fetcher.py
    print(f"\n[PHASE 3] ANALYSE DES BUGS DANS fetcher.py")
    print("-" * 60)
    
    print("\n  [BUG #1] alt_baro = 'ground' (string)")
    print("     L'API adsb.lol renvoie parfois alt_baro='ground' quand l'avion")
    print("     est au sol. Le code fetcher.py (ligne 137) verifie:")
    print("       elif live_data.get('alt_baro') is None and ...")
    print("     Mais 'ground' is not None => True => l'avion est considere EN VOL!")
    print("     IMPACT: Faux positifs -- avions au sol comptes comme en vol")
    
    print("\n  [BUG #2] Doublons de vols dans poll.log")
    print("     poll.log: N628TS a 3 'Nouveau vol' en 3 secondes (lignes 53-55)")
    print("     poll.log: 3C-EGE a 3 'Nouveau vol' consecutifs (lignes 77-79)")
    print("     poll.log: TJ-QCA a 4 'Nouveau vol' consecutifs (lignes 96-101)")
    print("     CAUSE: race condition dans la boucle poll_all_fleet()")
    print("     Le commit final est hors de la boucle for, mais db.add()")
    print("     n'est pas suivi d'un flush immediat => vol_ouvert.query")
    print("     ne trouve pas le vol qui vient d'etre cree.")
    print("     IMPACT: Vols dupliques en base de donnees")
    
    print("\n  [BUG #3] Vols fermes avec duree 0 minutes")
    print("     poll.log: N628TS ferme 2 fois avec 'Duree: 0.0 min' (lignes 73-74)")
    print("     CAUSE: Les doublons de vols sont fermes immediatement car ils")
    print("     n'ont pas de positions -> last_update = departure_time")
    
    print("\n  [BUG #4] Ghost Fleet (Faux positifs)")
    print("     Le scan_ghost_fleet detecte des jets de luxe autour des capitales")
    print("     mais ne verifie pas si ce sont des vols commerciaux ou prives")
    print("     legitimes sans rapport avec les VIPs.")
    
    if dupes:
        print(f"\n  [BUG #5] Doublons ICAO24 dans la flotte ({len(dupes)})")
        for icao, owners in dupes.items():
            print(f"     {icao} est liste {len(owners)} fois: {', '.join(owners)}")
        print("     IMPACT: Le meme avion genere des vols pour plusieurs pays")
    
    # Phase 4: Resume
    print(f"\n{'='*80}")
    print("  RESUME FINAL")
    print(f"{'='*80}")
    print(f"  Avions en base         : {total_jets}")
    print(f"  Trackables (ICAO24)    : {jets_with_icao}")
    print(f"  Non-trackables         : {jets_no_icao}")
    print(f"  Detectes par API       : {jets_detected}")
    print(f"    +-- En vol           : {jets_airborne}")
    print(f"    +-- Au sol           : {jets_on_ground}")
    print(f"  Hors radar             : {jets_not_detected}")
    print(f"  Bugs identifies        : {len(bugs_found)}")
    coverage = round(jets_detected/max(jets_with_icao,1)*100, 1)
    print(f"  Taux de couverture     : {jets_detected}/{jets_with_icao} ({coverage}%)")
    
    if bugs_found:
        print(f"\n  BUGS CRITIQUES ({len(bugs_found)}):")
        for i, bug in enumerate(bugs_found, 1):
            print(f"     {i}. {bug}")
    
    # Sauvegarder le rapport JSON
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_jets": total_jets,
            "trackable": jets_with_icao,
            "not_trackable": jets_no_icao,
            "detected": jets_detected,
            "airborne": jets_airborne,
            "on_ground": jets_on_ground,
            "offline": jets_not_detected,
            "bugs_count": len(bugs_found),
            "coverage_pct": coverage
        },
        "bugs": bugs_found,
        "duplicates": {k: v for k, v in duplicate_icao.items() if len(v) > 1},
        "results": results
    }
    
    report_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scratch", "adsb_diagnostic_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n  Rapport sauvegarde: {report_path}")
    print("=" * 80)
    
    return report

if __name__ == "__main__":
    run_diagnostic()
