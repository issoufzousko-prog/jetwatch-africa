"""
Diagnostic ADS-B : vérifie la détection de chaque avion de la flotte présidentielle.
Interroge l'API adsb.lol pour chaque ICAO24 et affiche le statut.
"""
import json
import time
import requests

# Charger la flotte
with open("data/jets_africains.json", "r", encoding="utf-8") as f:
    flottes = json.load(f)

print("=" * 90)
print(f"{'PAYS':<22} {'DIRIGEANT':<22} {'ICAO24':<10} {'TAIL':<12} {'STATUT':<12} {'POS'}")
print("=" * 90)

total_jets = 0
detected = 0
in_flight = 0
on_ground = 0
no_signal = 0
errors = 0

for pays_data in flottes:
    pays = pays_data["pays"]
    dirigeant = pays_data.get("dirigeant", "?")
    flotte = pays_data.get("flotte", [])
    
    for jet in flotte:
        icao24 = jet.get("icao24", "").lower()
        tail = jet.get("tail_number", "?")
        verifie = jet.get("verifie", False)
        total_jets += 1
        
        if not icao24:
            print(f"{pays:<22} {dirigeant:<22} {'N/A':<10} {tail:<12} {'NO ICAO':<12} —")
            continue
        
        # Rate limit
        time.sleep(1.0)
        
        try:
            url = f"https://api.adsb.lol/v2/hex/{icao24}"
            resp = requests.get(url, headers={"Accept": "application/json"}, timeout=10)
            
            if resp.status_code != 200:
                print(f"{pays:<22} {dirigeant:<22} {icao24:<10} {tail:<12} {'HTTP ' + str(resp.status_code):<12} —")
                errors += 1
                continue
            
            data = resp.json()
            ac_list = data.get("ac", [])
            
            if len(ac_list) == 0:
                print(f"{pays:<22} {dirigeant:<22} {icao24:<10} {tail:<12} {'HORS RADAR':<12} —")
                no_signal += 1
                continue
            
            ac = ac_list[0]
            is_grounded = ac.get("ground", ac.get("GND", None))
            alt = ac.get("alt_baro", ac.get("baro_alt", None))
            gs = ac.get("gs", None)
            lat = ac.get("lat", None)
            lon = ac.get("lon", None)
            flight = str(ac.get("flight", "")).strip()
            ac_type = ac.get("t", "?")
            
            # Determine status
            if is_grounded is True or (alt is None and gs is None):
                status = "AU SOL"
                on_ground += 1
            else:
                status = "EN VOL"
                in_flight += 1
            
            detected += 1
            pos_str = f"lat={lat}, lon={lon}, alt={alt}ft, gs={gs}kts" if lat else "—"
            print(f"{pays:<22} {dirigeant:<22} {icao24:<10} {tail:<12} {status:<12} {pos_str}")
            
        except requests.exceptions.Timeout:
            print(f"{pays:<22} {dirigeant:<22} {icao24:<10} {tail:<12} {'TIMEOUT':<12} —")
            errors += 1
        except Exception as e:
            print(f"{pays:<22} {dirigeant:<22} {icao24:<10} {tail:<12} {'ERREUR':<12} {str(e)[:40]}")
            errors += 1

print("=" * 90)
print(f"\n📊 RÉSUMÉ DU DIAGNOSTIC ADS-B")
print(f"   Total jets dans la flotte : {total_jets}")
print(f"   Détectés par l'API        : {detected} ({detected/total_jets*100:.0f}%)" if total_jets > 0 else "")
print(f"     ✈️  En vol               : {in_flight}")
print(f"     🛬 Au sol                : {on_ground}")
print(f"   Hors radar (transpondeur off) : {no_signal}")
print(f"   Erreurs réseau            : {errors}")
print(f"\n💡 NOTE : Les avions 'HORS RADAR' ne sont pas un bug.")
print(f"   Cela signifie que le transpondeur ADS-B est éteint (avion parqué,")
print(f"   en maintenance, ou volontairement invisible).")
