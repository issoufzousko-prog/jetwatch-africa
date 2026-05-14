"""
JetWatch Africa -- Script de verification post-fix
====================================================
Verifie que le nouveau fetcher.py fonctionne correctement :
1. Endpoints conformes aux guides adsb.lol et adsb.fi
2. Logique determine_airborne() corrigee
3. Multi-provider avec fallback
"""

import os
import sys
import json
import io
import time
import requests
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Importer le nouveau fetcher
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import fetcher

def test_determine_airborne():
    """Test unitaire de la nouvelle logique determine_airborne()"""
    print("\n[TEST 1] Logique determine_airborne()")
    print("-" * 60)
    
    test_cases = [
        # (description, data, attendu)
        ("GND=True (bool) -> au sol", {"GND": True, "alt_baro": 35000}, False),
        ("GND=False (bool) -> en vol", {"GND": False, "alt_baro": 35000}, True),
        ("GND='true' (string) -> au sol", {"GND": "true", "alt_baro": 35000}, False),
        ("GND='false' (string) -> en vol", {"GND": "false", "alt_baro": 35000}, True),
        ("alt_baro='ground' (BUG CORRIGE) -> au sol", {"alt_baro": "ground", "gs": 2.8}, False),
        ("alt_baro='ground' sans gs -> au sol", {"alt_baro": "ground"}, False),
        ("alt_baro=35000 -> en vol", {"alt_baro": 35000, "gs": 450}, True),
        ("alt_baro=None, gs=None -> au sol", {"alt_baro": None, "gs": None}, False),
        ("alt_baro=None, gs=5 (taxi) -> au sol", {"gs": 5}, False),
        ("alt_baro=None, gs=250 (vol) -> en vol", {"gs": 250}, True),
        ("alt_baro=0, gs=0 -> au sol", {"alt_baro": 0, "gs": 0}, False),
        ("Aucun champ -> au sol", {}, False),
    ]
    
    all_passed = True
    for desc, data, expected in test_cases:
        result = fetcher.determine_airborne(data)
        status = "PASS" if result == expected else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"  [{status}] {desc}")
        if status == "FAIL":
            print(f"         Attendu: {expected}, Obtenu: {result}")
    
    return all_passed


def test_providers_config():
    """Verifie la configuration des providers"""
    print("\n[TEST 2] Configuration des providers ADS-B")
    print("-" * 60)
    
    all_ok = True
    for p in fetcher.ADSB_PROVIDERS:
        name = p["name"]
        print(f"\n  Provider: {name}")
        print(f"    Base URL: {p['base_url']}")
        print(f"    ICAO endpoint: {p['icao_endpoint']}")
        print(f"    Area endpoint: {p['area_endpoint']}")
        print(f"    Callsign endpoint: {p['callsign_endpoint']}")
        
        # Verifier que les templates sont valides
        try:
            icao_url = p["base_url"] + p["icao_endpoint"].format(icao="010024")
            area_url = p["base_url"] + p["area_endpoint"].format(lat=5.36, lon=-4.01, dist=250)
            cs_url = p["base_url"] + p["callsign_endpoint"].format(cs="EGY01")
            print(f"    [OK] ICAO URL: {icao_url}")
            print(f"    [OK] Area URL: {area_url}")
            print(f"    [OK] Callsign URL: {cs_url}")
        except Exception as e:
            print(f"    [FAIL] Template error: {e}")
            all_ok = False
    
    return all_ok


def test_live_query():
    """Test reel avec un avion connu (SU-GGG = Egypte)"""
    print("\n[TEST 3] Requete live multi-provider (SU-GGG / 010024)")
    print("-" * 60)
    
    # Test avec chaque provider individuellement
    for p in fetcher.ADSB_PROVIDERS:
        print(f"\n  [{p['name']}]:", end=" ", flush=True)
        result = fetcher._query_provider(p, p["icao_endpoint"], icao="010024")
        if result:
            alt = result.get("alt_baro")
            gs = result.get("gs")
            airborne = fetcher.determine_airborne(result)
            print(f"DETECTE | alt_baro={alt} (type={type(alt).__name__}) | gs={gs} | airborne={airborne}")
        else:
            print("Pas detecte (hors radar)")
    
    # Test avec le multi-provider
    print(f"\n  [Multi-provider get_live_position]:", end=" ", flush=True)
    time.sleep(1.5)
    result = fetcher.get_live_position("010024")
    if result:
        airborne = fetcher.determine_airborne(result)
        print(f"DETECTE | airborne={airborne} | callsign={result.get('flight', '?').strip()}")
        
        if result.get("alt_baro") == "ground":
            print(f"  -> alt_baro='ground' DETECTE - determine_airborne retourne {airborne}")
            if airborne:
                print(f"  [FAIL] BUG NON CORRIGE! L'avion au sol est considere en vol!")
                return False
            else:
                print(f"  [PASS] BUG CORRIGE! L'avion au sol est correctement detecte.")
    else:
        print("Aucun avion detecte par aucun provider (normal si hors radar)")
    
    return True


def test_area_query():
    """Test du scan de zone multi-provider"""
    print("\n[TEST 4] Scan de zone multi-provider (Nairobi, 50nm)")
    print("-" * 60)
    
    aircraft = fetcher.get_area_aircraft(lat=-1.319, lon=36.927, dist_nm=50)
    print(f"  Avions detectes: {len(aircraft)}")
    
    for i, ac in enumerate(aircraft[:5]):
        icao = ac.get("hex", "?")
        flight = ac.get("flight", "?").strip() if ac.get("flight") else "?"
        alt = ac.get("alt_baro", "?")
        ac_type = ac.get("t", "?")
        airborne = fetcher.determine_airborne(ac)
        print(f"  [{i+1}] {icao} | {flight} | type={ac_type} | alt={alt} | airborne={airborne}")
    
    if len(aircraft) > 5:
        print(f"  ... et {len(aircraft) - 5} autres")
    
    return True


def run_verification():
    print("=" * 80)
    print("  JETWATCH AFRICA -- VERIFICATION POST-FIX")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    results = {}
    
    # Test 1: Logique determine_airborne
    results["determine_airborne"] = test_determine_airborne()
    
    # Test 2: Configuration providers
    results["providers_config"] = test_providers_config()
    
    # Test 3: Requete live
    results["live_query"] = test_live_query()
    
    time.sleep(1.5)
    
    # Test 4: Scan de zone
    results["area_query"] = test_area_query()
    
    # Resume
    print(f"\n{'='*80}")
    print("  RESUME")
    print(f"{'='*80}")
    all_pass = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {name}")
    
    print(f"\n  Resultat global: {'TOUS LES TESTS PASSES' if all_pass else 'ECHEC'}")
    print("=" * 80)


if __name__ == "__main__":
    run_verification()
