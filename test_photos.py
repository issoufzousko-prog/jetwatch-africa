import requests, json

with open('data/jets_africains.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for e in data:
    url = e.get('photo_url', '')
    if url:
        try:
            r = requests.head(url, timeout=8, headers={'User-Agent': 'Mozilla/5.0'}, allow_redirects=True)
            print(f"{e['pays']}: HTTP {r.status_code}")
        except Exception as ex:
            print(f"{e['pays']}: ERROR {ex}")
