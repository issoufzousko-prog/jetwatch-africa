import sqlite3
conn = sqlite3.connect("jetwatch.db")
c = conn.cursor()

# Lister les tables
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("=== TABLES ===")
for t in c.fetchall():
    print(t[0])

print()
# Structure de chaque table
for tbl in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
    tbl = tbl[0]
    c.execute(f"PRAGMA table_info({tbl})")
    cols = c.fetchall()
    print(f"--- {tbl} ---")
    for col in cols:
        print(f"  {col[1]} ({col[2]})")

print()
print("=== TARGETS (5 premiers) ===")
c.execute("SELECT * FROM targets LIMIT 5")
for r in c.fetchall():
    print(r)

print()
print("=== VOLS (10 premiers) ===")
c.execute("SELECT * FROM flights LIMIT 10")
for r in c.fetchall():
    print(r)

print()
print("=== NOMBRE TOTAL DE VOLS ===")
c.execute("SELECT COUNT(*) FROM flights")
print(c.fetchone()[0])

conn.close()
