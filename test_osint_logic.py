import osint_agent
import json

print("=" * 70)
print("TEST OSINT GRAPH TRAVERSAL - Alassane Ouattara -> Mougins")
print("=" * 70)

res = osint_agent.search_public_records("Alassane Ouattara", "Mougins", "Cote d'Ivoire")

print("\n\n" + "=" * 70)
print("RAPPORT FINAL (JSON)")
print("=" * 70)
print(json.dumps(res, indent=2, ensure_ascii=False))
