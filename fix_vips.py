import json
import requests

def get_photo(name):
    for lang in ['en', 'fr']:
        try:
            url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{name.replace(' ', '_')}"
            resp = requests.get(url, timeout=8, headers={'User-Agent': 'JetWatch/1.0 (contact@jetwatch.local)'})
            if resp.status_code == 200:
                data = resp.json()
                photo = data.get('thumbnail', {}).get('source', '')
                original = data.get('originalimage', {}).get('source', '')
                if photo or original:
                    return original or photo
        except:
            pass
    return ''

with open('data/jets_africains.json', 'r', encoding='utf-8') as f:
    flottes = json.load(f)

for item in flottes:
    if item.get('pays') in ['Elon Musk', 'Mark Zuckerberg', 'Kim Kardashian', 'Bernard Arnault']:
        item['photo_url'] = get_photo(item['pays'])

with open('data/jets_africains.json', 'w', encoding='utf-8') as f:
    json.dump(flottes, f, ensure_ascii=False, indent=2)
