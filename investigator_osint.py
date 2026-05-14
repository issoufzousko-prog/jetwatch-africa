"""
JetWatch Africa — Couche 3 : Collecte OSINT & Enquête Destination

Ce module effectue des recherches web automatisées via DuckDuckGo pour collecter
des données publiques sur un dirigeant et son entourage, à la destination du vol.

Sources consultées :
- Presse (RFI, AFP, Reuters, Jeune Afrique)
- Agendas officiels (présidence, primature)
- Registres fonciers et sociétés (OpenCorporates, ICIJ)
- Bases de données PEP (Politically Exposed Persons)
"""

import time
from duckduckgo_search import DDGS


def _safe_search(query, max_results=5):
    """Effectue une recherche DuckDuckGo avec gestion d'erreurs et rate limiting."""
    try:
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_results))
        time.sleep(1)  # Rate limiting
        return results
    except Exception as e:
        print(f"[OSINT] Erreur recherche '{query[:60]}...': {e}")
        return []


def search_press(dirigeant, destination, date_vol):
    """
    Couche 3 — Recherche presse locale et internationale.
    Cherche des articles mentionnant le dirigeant à la destination à la date du vol.
    """
    queries = [
        f'"{dirigeant}" "{destination}" {date_vol}',
        f'"{dirigeant}" visite "{destination}" site:rfi.fr OR site:jeuneafrique.com',
        f'"{dirigeant}" "{destination}" sommet OR conférence OR visite officielle',
        f'"{dirigeant}" voyage "{destination}" {date_vol[:7]}',
    ]

    all_results = []
    for q in queries:
        results = _safe_search(q, max_results=3)
        for r in results:
            all_results.append({
                "title": r.get("title", ""),
                "body": r.get("body", ""),
                "url": r.get("href", ""),
                "query": q
            })

    return all_results


def search_official_agenda(dirigeant, pays, date_vol):
    """
    Couche 3 — Recherche de l'agenda officiel du dirigeant.
    Vérifie s'il y avait un événement officiel prévu à cette date.
    """
    queries = [
        f'agenda officiel "{dirigeant}" {date_vol}',
        f'présidence "{pays}" agenda {date_vol[:7]}',
        f'"{dirigeant}" programme officiel {date_vol}',
        f'"{pays}" sommet conférence {date_vol[:7]}',
    ]

    all_results = []
    for q in queries:
        results = _safe_search(q, max_results=3)
        for r in results:
            all_results.append({
                "title": r.get("title", ""),
                "body": r.get("body", ""),
                "url": r.get("href", ""),
                "query": q
            })

    return all_results


def search_assets(noms_reseau, destination):
    """
    Couche 3 — Recherche d'actifs immobiliers et sociétés à la destination.
    Cherche pour chaque membre du réseau (famille, entourage, proxy).
    """
    all_results = []

    for nom in noms_reseau:
        queries = [
            f'"{nom}" property "{destination}"',
            f'"{nom}" real estate "{destination}"',
            f'"{nom}" immobilier "{destination}"',
            f'"{nom}" villa OR appartement "{destination}"',
            f'site:opencorporates.com "{nom}"',
        ]

        for q in queries:
            results = _safe_search(q, max_results=2)
            for r in results:
                all_results.append({
                    "person": nom,
                    "title": r.get("title", ""),
                    "body": r.get("body", ""),
                    "url": r.get("href", ""),
                    "query": q
                })

    return all_results


def search_offshore_leaks(noms_reseau):
    """
    Couche 3 — Recherche dans les bases de données offshore (ICIJ, OCCRP).
    """
    all_results = []

    for nom in noms_reseau:
        queries = [
            f'site:offshoreleaks.icij.org "{nom}"',
            f'"{nom}" panama papers OR pandora papers OR paradise papers',
            f'"{nom}" offshore OR shell company OR société écran',
            f'site:opencorporates.com "{nom}"',
            f'"{nom}" OCCRP OR aleph investigation',
        ]

        for q in queries:
            results = _safe_search(q, max_results=2)
            for r in results:
                all_results.append({
                    "person": nom,
                    "title": r.get("title", ""),
                    "body": r.get("body", ""),
                    "url": r.get("href", ""),
                    "query": q
                })

    return all_results


def build_family_tree(dirigeant, pays):
    """
    Couche 3 — Construction de l'arbre généalogique et du réseau d'entourage.
    Recherche les membres de la famille, l'entourage politique, et les prête-noms.
    """
    queries = [
        f'"{dirigeant}" épouse OR femme OR wife',
        f'"{dirigeant}" enfants OR fils OR fille OR children',
        f'"{dirigeant}" frère OR sœur OR brother OR sister',
        f'"{dirigeant}" famille OR family',
        f'"{dirigeant}" directeur cabinet OR conseiller spécial',
        f'"{dirigeant}" proche OR entourage OR associé',
        f'"{dirigeant}" homme affaires OR businessman friend',
        f'ministre finances "{pays}" {dirigeant}',
        f'garde présidentielle "{pays}" chef',
        f'"{dirigeant}" fortune OR patrimoine OR wealth',
    ]

    all_results = []
    for q in queries:
        results = _safe_search(q, max_results=3)
        for r in results:
            all_results.append({
                "title": r.get("title", ""),
                "body": r.get("body", ""),
                "url": r.get("href", ""),
                "query": q
            })

    return all_results


def search_sanctions(dirigeant, pays):
    """
    Couche 3 — Recherche de sanctions internationales.
    OFAC, UE, ONU, ECOWAS.
    """
    queries = [
        f'"{dirigeant}" sanctions OFAC OR EU OR ONU',
        f'"{dirigeant}" sanctioned OR blacklisted',
        f'"{pays}" dirigeant sanctions internationales',
        f'"{dirigeant}" politically exposed person PEP',
    ]

    all_results = []
    for q in queries:
        results = _safe_search(q, max_results=2)
        for r in results:
            all_results.append({
                "title": r.get("title", ""),
                "body": r.get("body", ""),
                "url": r.get("href", ""),
                "query": q
            })

    return all_results


def gather_all_osint(dirigeant, pays, destination, date_vol, noms_reseau=None):
    """
    Point d'entrée principal de la Couche 3.
    Collecte toutes les données OSINT disponibles.

    Args:
        dirigeant: Nom du dirigeant
        pays: Pays du dirigeant
        destination: Ville/pays de destination
        date_vol: Date au format YYYY-MM-DD
        noms_reseau: Liste de noms à rechercher (famille, entourage)

    Returns:
        dict avec toutes les données collectées par catégorie
    """
    if noms_reseau is None:
        noms_reseau = [dirigeant]

    print(f"[OSINT] Début de la collecte pour {dirigeant} → {destination} ({date_vol})")

    press = search_press(dirigeant, destination, date_vol)
    print(f"[OSINT] Presse: {len(press)} résultats")

    agenda = search_official_agenda(dirigeant, pays, date_vol)
    print(f"[OSINT] Agenda: {len(agenda)} résultats")

    family = build_family_tree(dirigeant, pays)
    print(f"[OSINT] Arbre familial: {len(family)} résultats")

    assets = search_assets(noms_reseau, destination)
    print(f"[OSINT] Actifs: {len(assets)} résultats")

    offshore = search_offshore_leaks(noms_reseau)
    print(f"[OSINT] Offshore: {len(offshore)} résultats")

    sanctions = search_sanctions(dirigeant, pays)
    print(f"[OSINT] Sanctions: {len(sanctions)} résultats")

    total = len(press) + len(agenda) + len(family) + len(assets) + len(offshore) + len(sanctions)
    print(f"[OSINT] Collecte terminée: {total} résultats au total")

    return {
        "press": press,
        "official_agenda": agenda,
        "family_tree": family,
        "assets_at_destination": assets,
        "offshore_leaks": offshore,
        "sanctions": sanctions,
        "metadata": {
            "dirigeant": dirigeant,
            "pays": pays,
            "destination": destination,
            "date_vol": date_vol,
            "noms_recherches": noms_reseau,
            "total_results": total
        }
    }
