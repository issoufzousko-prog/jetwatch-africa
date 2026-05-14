import sqlite3
conn = sqlite3.connect("jetwatch.db")
c = conn.cursor()

# Flotte du Nigeria
print("=== FLOTTE NIGERIA (SQL) ===")
c.execute("""SELECT tf.icao24, tf.tail_number, tf.description, tf.verifie
             FROM target_fleets tf
             JOIN targets t ON tf.target_id = t.id
             WHERE LOWER(t.pays) LIKE '%nigeria%' """)
for r in c.fetchall():
    print(r)

# Target Nigeria
print()
print("=== TARGET NIGERIA ===")
c.execute("SELECT * FROM targets WHERE LOWER(pays) LIKE '%nigeria%'")
for r in c.fetchall():
    print(r)

# Vols associes au Nigeria
print()
print("=== VOLS NIGERIA ===")
c.execute("""SELECT f.id, f.icao24, f.callsign, f.departure_time, f.arrival_time, f.duration_minutes
             FROM flights f
             JOIN target_fleets tf ON LOWER(f.icao24) = LOWER(tf.icao24)
             JOIN targets t ON tf.target_id = t.id
             WHERE LOWER(t.pays) LIKE '%nigeria%' """)
for r in c.fetchall():
    print(r)

# Verifier aussi le fichier JSON
import json, os
json_path = os.path.join("data", "jets_africains.json")
if os.path.exists(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for item in data:
        if "nigeria" in item.get("pays", "").lower():
            print()
            print("=== NIGERIA DANS JSON ===")
            print(json.dumps(item, indent=2, ensure_ascii=False))
            break
else:
    print("Fichier JSON introuvable:", json_path)

conn.close()
