"""
Entity Resolver v4 — Multi-Source Cross-Reference Engine
========================================================
Algorithmes de croisement pour relier personnes ↔ sociétés ↔ biens.
Sources : Wikidata SPARQL, Pappers (gratuit), OpenCorporates, OCCRP Aleph,
           DVF (data.gouv.fr), DuckDuckGo.

Chaque résultat inclut un score de confiance et la source vérifiable.
Le LLM ReAct Agent utilise ces fonctions comme des outils.
"""

import requests
import time
import json
import re
from typing import Optional
from rapidfuzz import fuzz, process
from duckduckgo_search import DDGS

# Rate limiting simple
_last_request_time = {}
MIN_REQUEST_INTERVAL = 1.0  # secondes entre requêtes pour la même source


def _rate_limit(source: str, interval: float = MIN_REQUEST_INTERVAL):
    """Respecte un délai minimum entre les requêtes à une même source."""
    now = time.time()
    last = _last_request_time.get(source, 0)
    wait = interval - (now - last)
    if wait > 0:
        time.sleep(wait)
    _last_request_time[source] = time.time()


# ════════════════════════════════════════════════════════════════════════
# 1. PersonResolver — Wikidata + DuckDuckGo
# ════════════════════════════════════════════════════════════════════════

class PersonResolver:
    """Résout les relations familiales et associatives d'une personne."""
    
    WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
    HEADERS = {"User-Agent": "JetwatchAfrica/4.0 OSINT Investigation Tool"}
    
    # Propriétés Wikidata pour les relations familiales
    WIKIDATA_FAMILY_PROPS = {
        "P26": "épouse/époux",
        "P40": "enfant",
        "P22": "père",
        "P25": "mère",
        "P3373": "frère/sœur",
        "P451": "partenaire",
        "P1038": "famille",
    }
    
    def search_wikidata(self, name: str) -> dict:
        """
        Cherche une personne dans Wikidata et retourne ses relations familiales.
        Utilise SPARQL pour extraire les propriétés familiales structurées.
        
        Returns:
            {
                "found": bool,
                "wikidata_id": str,
                "description": str,
                "relations": [{"name": str, "relation": str, "wikidata_id": str}],
                "positions": [str],  # Positions politiques
                "source_url": str,
                "confidence": float
            }
        """
        _rate_limit("wikidata", 2.0)
        
        # D'abord chercher l'entité par nom
        search_url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbsearchentities",
            "search": name,
            "language": "fr",
            "uselang": "fr",
            "type": "item",
            "limit": 3,
            "format": "json"
        }
        
        try:
            resp = requests.get(search_url, params=params, headers=self.HEADERS, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            results = data.get("search", [])
            if not results:
                # Essayer en anglais
                params["language"] = "en"
                params["uselang"] = "en"
                resp = requests.get(search_url, params=params, headers=self.HEADERS, timeout=10)
                data = resp.json()
                results = data.get("search", [])
            
            if not results:
                return {"found": False, "relations": [], "source_url": ""}
            
            # Prendre le premier résultat (le plus pertinent)
            entity_id = results[0]["id"]
            description = results[0].get("description", "")
            
            # Maintenant récupérer les relations via SPARQL
            relations = self._query_family_sparql(entity_id)
            positions = self._query_positions_sparql(entity_id)
            
            return {
                "found": True,
                "wikidata_id": entity_id,
                "description": description,
                "relations": relations,
                "positions": positions,
                "source_url": f"https://www.wikidata.org/wiki/{entity_id}",
                "confidence": 0.75,
            }
            
        except Exception as e:
            print(f"[RESOLVER] Erreur Wikidata pour '{name}': {e}")
            return {"found": False, "relations": [], "source_url": "", "error": str(e)}
    
    def _query_family_sparql(self, entity_id: str) -> list:
        """Requête SPARQL pour les relations familiales."""
        # Construire la requête pour toutes les propriétés familiales
        prop_unions = "\n      UNION\n      ".join([
            f'{{ wd:{entity_id} wdt:{prop} ?related . BIND("{rel}" AS ?relType) }}'
            for prop, rel in self.WIKIDATA_FAMILY_PROPS.items()
        ])
        
        query = f"""
        SELECT ?related ?relatedLabel ?relType WHERE {{
            {prop_unions}
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "fr,en". }}
        }}
        LIMIT 20
        """
        
        try:
            resp = requests.get(
                self.WIKIDATA_ENDPOINT,
                params={"query": query, "format": "json"},
                headers={**self.HEADERS, "Accept": "application/sparql-results+json"},
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            
            relations = []
            for binding in data.get("results", {}).get("bindings", []):
                related_uri = binding.get("related", {}).get("value", "")
                related_id = related_uri.split("/")[-1] if related_uri else ""
                relations.append({
                    "name": binding.get("relatedLabel", {}).get("value", "Inconnu"),
                    "relation": binding.get("relType", {}).get("value", "lié"),
                    "wikidata_id": related_id,
                })
            
            return relations
            
        except Exception as e:
            print(f"[RESOLVER] Erreur SPARQL famille: {e}")
            return []
    
    def _query_positions_sparql(self, entity_id: str) -> list:
        """Requête SPARQL pour les positions politiques (P39)."""
        query = f"""
        SELECT ?positionLabel WHERE {{
            wd:{entity_id} wdt:P39 ?position .
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "fr,en". }}
        }}
        LIMIT 10
        """
        
        try:
            resp = requests.get(
                self.WIKIDATA_ENDPOINT,
                params={"query": query, "format": "json"},
                headers={**self.HEADERS, "Accept": "application/sparql-results+json"},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            
            return [
                b.get("positionLabel", {}).get("value", "")
                for b in data.get("results", {}).get("bindings", [])
            ]
            
        except Exception:
            return []
    
    def search_duckduckgo(self, query: str, max_results: int = 5) -> list:
        """
        Recherche textuelle via DuckDuckGo. Retourne les résultats bruts
        que le LLM analysera lui-même (pas de regex).
        """
        _rate_limit("duckduckgo")
        
        results = []
        try:
            with DDGS() as ddgs:
                raw = list(ddgs.text(query, max_results=max_results, region='fr-fr'))
                for r in raw:
                    results.append({
                        "title": r.get("title", ""),
                        "body": r.get("body", ""),
                        "url": r.get("href", ""),
                    })
        except Exception as e:
            print(f"[RESOLVER] Erreur DuckDuckGo: {e}")
        
        return results
    
    def search_images(self, query: str, max_results: int = 4) -> list:
        """Recherche d'images via DuckDuckGo."""
        _rate_limit("duckduckgo_images")
        
        images = []
        try:
            with DDGS() as ddgs:
                raw = list(ddgs.images(query, max_results=max_results))
                for img in raw:
                    images.append({
                        "url": img.get("image", ""),
                        "title": img.get("title", ""),
                        "source": img.get("source", ""),
                        "thumbnail": img.get("thumbnail", ""),
                    })
        except Exception as e:
            print(f"[RESOLVER] Erreur Images: {e}")
        
        return images


# ════════════════════════════════════════════════════════════════════════
# 2. CorporateResolver — Pappers + OpenCorporates + OCCRP Aleph
# ════════════════════════════════════════════════════════════════════════

class CorporateResolver:
    """Recherche dans les registres d'entreprises."""
    
    PAPPERS_BASE = "https://api.pappers.fr/v2"
    OPENCORPORATES_BASE = "https://api.opencorporates.com/v0.4"
    ALEPH_BASE = "https://aleph.occrp.org/api/2"
    
    def __init__(self, pappers_key: str = "", aleph_key: str = ""):
        self.pappers_key = pappers_key
        self.aleph_key = aleph_key
    
    def search_pappers(self, name: str) -> dict:
        """
        Recherche une personne/société dans Pappers (registre français).
        API gratuite : 100 requêtes/jour sans clé.
        
        Returns:
            {
                "found": bool,
                "companies": [{
                    "name": str,
                    "siren": str,
                    "type": str (SCI, SAS, SARL...),
                    "role": str (dirigeant, associé, bénéficiaire),
                    "address": str,
                    "status": str (active/radiée),
                    "source_url": str,
                }],
                "confidence": float
            }
        """
        _rate_limit("pappers", 2.0)
        
        # Recherche par dirigeant (gratuit sans clé via recherche basique)
        try:
            params = {
                "q": name,
                "par_page": 5,
            }
            if self.pappers_key:
                params["api_token"] = self.pappers_key
            
            resp = requests.get(
                f"{self.PAPPERS_BASE}/recherche",
                params=params,
                timeout=10
            )
            
            if resp.status_code == 401 or resp.status_code == 403:
                # Fallback: recherche via DuckDuckGo sur pappers.fr
                return self._search_pappers_fallback(name)
            
            resp.raise_for_status()
            data = resp.json()
            
            companies = []
            for result in data.get("resultats", [])[:5]:
                companies.append({
                    "name": result.get("nom_entreprise", ""),
                    "siren": result.get("siren", ""),
                    "type": result.get("forme_juridique", ""),
                    "role": "dirigeant/associé",
                    "address": result.get("siege", {}).get("adresse_ligne_1", ""),
                    "city": result.get("siege", {}).get("ville", ""),
                    "status": "active" if result.get("entreprise_cessee") == False else "radiée",
                    "source_url": f"https://www.pappers.fr/entreprise/{result.get('siren', '')}",
                })
            
            return {
                "found": len(companies) > 0,
                "companies": companies,
                "confidence": 0.85 if companies else 0.0,
            }
            
        except Exception as e:
            print(f"[RESOLVER] Erreur Pappers pour '{name}': {e}")
            return self._search_pappers_fallback(name)
    
    def _search_pappers_fallback(self, name: str) -> dict:
        """Fallback: cherche sur pappers.fr via DuckDuckGo."""
        resolver = PersonResolver()
        results = resolver.search_duckduckgo(
            f'site:pappers.fr "{name}" dirigeant OR associé OR bénéficiaire',
            max_results=3
        )
        
        companies = []
        for r in results:
            # Extraire le SIREN du titre/URL si possible
            siren_match = re.search(r'(\d{9})', r.get("url", ""))
            companies.append({
                "name": r.get("title", "").replace(" - Pappers", ""),
                "siren": siren_match.group(1) if siren_match else "",
                "type": "inconnu",
                "role": "mentionné",
                "source_url": r.get("url", ""),
            })
        
        return {
            "found": len(companies) > 0,
            "companies": companies,
            "confidence": 0.50 if companies else 0.0,
            "method": "fallback_duckduckgo",
        }
    
    def search_opencorporates(self, name: str, jurisdiction: str = "") -> dict:
        """
        Recherche dans OpenCorporates (registres internationaux).
        API gratuite : pas de clé nécessaire pour la recherche basique.
        """
        _rate_limit("opencorporates", 2.0)
        
        try:
            params = {"q": name, "per_page": 5}
            if jurisdiction:
                params["jurisdiction_code"] = jurisdiction
            
            resp = requests.get(
                f"{self.OPENCORPORATES_BASE}/companies/search",
                params=params,
                headers={"User-Agent": "JetwatchAfrica/4.0"},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            
            companies = []
            for item in data.get("results", {}).get("companies", [])[:5]:
                company = item.get("company", {})
                companies.append({
                    "name": company.get("name", ""),
                    "company_number": company.get("company_number", ""),
                    "jurisdiction": company.get("jurisdiction_code", ""),
                    "status": company.get("current_status", ""),
                    "incorporation_date": company.get("incorporation_date", ""),
                    "address": company.get("registered_address_in_full", ""),
                    "source_url": company.get("opencorporates_url", ""),
                })
            
            return {
                "found": len(companies) > 0,
                "companies": companies,
                "confidence": 0.80 if companies else 0.0,
            }
            
        except Exception as e:
            print(f"[RESOLVER] Erreur OpenCorporates: {e}")
            return {"found": False, "companies": [], "confidence": 0.0, "error": str(e)}
    
    def search_aleph(self, name: str) -> dict:
        """
        Recherche dans OCCRP Aleph (Panama Papers, Pandora Papers, etc.).
        API publique, pas besoin de clé pour la recherche basique.
        """
        _rate_limit("aleph", 2.0)
        
        try:
            headers = {"User-Agent": "JetwatchAfrica/4.0"}
            if self.aleph_key:
                headers["Authorization"] = f"ApiKey {self.aleph_key}"
            
            resp = requests.get(
                f"{self.ALEPH_BASE}/search",
                params={"q": name, "limit": 5},
                headers=headers,
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            
            results_list = []
            for result in data.get("results", [])[:5]:
                properties = result.get("properties", {})
                results_list.append({
                    "name": properties.get("name", [""])[0] if isinstance(properties.get("name"), list) else properties.get("name", ""),
                    "schema": result.get("schema", ""),
                    "datasets": [d.get("label", "") for d in result.get("datasets", [])[:3]] if isinstance(result.get("datasets"), list) else [],
                    "countries": properties.get("country", []),
                    "addresses": properties.get("address", []),
                    "source_url": f"https://aleph.occrp.org/entities/{result.get('id', '')}",
                })
            
            return {
                "found": len(results_list) > 0,
                "results": results_list,
                "confidence": 0.70 if results_list else 0.0,
            }
            
        except Exception as e:
            print(f"[RESOLVER] Erreur OCCRP Aleph: {e}")
            return {"found": False, "results": [], "confidence": 0.0, "error": str(e)}


# ════════════════════════════════════════════════════════════════════════
# 3. PropertyResolver — DVF + Cadastre
# ════════════════════════════════════════════════════════════════════════

class PropertyResolver:
    """Recherche de biens immobiliers dans les bases publiques françaises."""
    
    DVF_API = "https://api.cquest.org/dvf"  # API DVF communautaire
    DVF_GOV_API = "https://apidf-preprod.cerema.fr/dvf_opendata/mutations"
    NOMINATIM_API = "https://nominatim.openstreetmap.org/search"
    
    def search_dvf(self, commune: str = "", section: str = "",
                   address: str = "", lat: float = None, lon: float = None,
                   radius_m: int = 500) -> dict:
        """
        Recherche dans DVF (Demandes de Valeurs Foncières).
        Base publique data.gouv.fr : historique des mutations immobilières (5 ans).
        
        Peut chercher par commune, adresse, ou coordonnées GPS.
        """
        _rate_limit("dvf", 1.5)
        
        try:
            # Stratégie 1 : Recherche par coordonnées GPS
            if lat and lon:
                params = {
                    "lat": lat,
                    "lon": lon,
                    "dist": radius_m,
                }
                resp = requests.get(
                    self.DVF_API,
                    params=params,
                    headers={"User-Agent": "JetwatchAfrica/4.0"},
                    timeout=10
                )
                resp.raise_for_status()
                data = resp.json()
                
                mutations = []
                for feature in data.get("features", [])[:10]:
                    props = feature.get("properties", {})
                    mutations.append({
                        "date": props.get("date_mutation", ""),
                        "nature": props.get("nature_mutation", ""),
                        "price": props.get("valeur_fonciere", ""),
                        "address": f"{props.get('adresse_numero', '')} {props.get('adresse_nom_voie', '')}",
                        "commune": props.get("nom_commune", ""),
                        "type_local": props.get("type_local", ""),
                        "surface": props.get("surface_reelle_bati", ""),
                        "terrain": props.get("surface_terrain", ""),
                        "section": props.get("code_section", ""),
                        "parcelle": props.get("numero_parcelle", ""),
                    })
                
                return {
                    "found": len(mutations) > 0,
                    "mutations": mutations,
                    "confidence": 0.80,
                    "source": "DVF (data.gouv.fr)",
                }
            
            # Stratégie 2 : Recherche par commune
            elif commune:
                # D'abord géocoder la commune
                coords = self._geocode(commune)
                if coords:
                    return self.search_dvf(lat=coords["lat"], lon=coords["lon"], radius_m=2000)
            
            # Stratégie 3 : Recherche par adresse
            elif address:
                coords = self._geocode(address)
                if coords:
                    return self.search_dvf(lat=coords["lat"], lon=coords["lon"], radius_m=200)
            
            return {"found": False, "mutations": [], "confidence": 0.0}
            
        except Exception as e:
            print(f"[RESOLVER] Erreur DVF: {e}")
            return {"found": False, "mutations": [], "confidence": 0.0, "error": str(e)}
    
    def _geocode(self, address: str) -> Optional[dict]:
        """Géocode une adresse via Nominatim (OpenStreetMap)."""
        _rate_limit("nominatim", 1.5)
        
        try:
            resp = requests.get(
                self.NOMINATIM_API,
                params={"q": address, "format": "json", "limit": 1},
                headers={"User-Agent": "JetwatchAfrica/4.0"},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            
            if data:
                return {
                    "lat": float(data[0]["lat"]),
                    "lon": float(data[0]["lon"]),
                    "display_name": data[0].get("display_name", ""),
                }
        except Exception:
            pass
        return None
    
    def geocode_address(self, address: str) -> Optional[dict]:
        """Public wrapper pour le géocodage."""
        return self._geocode(address)
    
    def search_property_duckduckgo(self, owner_name: str, city: str) -> list:
        """
        Recherche de biens immobiliers via DuckDuckGo.
        Retourne les résultats bruts pour le LLM.
        """
        resolver = PersonResolver()
        queries = [
            f'"{owner_name}" "{city}" villa OR résidence OR propriété OR immobilier',
            f'"{owner_name}" "{city}" SCI OR société OR acquisition OR achat',
        ]
        
        all_results = []
        for q in queries:
            results = resolver.search_duckduckgo(q, max_results=3)
            all_results.extend(results)
        
        return all_results


# ════════════════════════════════════════════════════════════════════════
# 4. FuzzyNameMatcher — Correspondance floue
# ════════════════════════════════════════════════════════════════════════

class FuzzyNameMatcher:
    """
    Correspondance floue de noms pour l'Entity Resolution.
    Gère les variations : "Ouattara" / "OUATTARA" / "Dramane Ouattara".
    """
    
    @staticmethod
    def match(name1: str, name2: str, threshold: float = 0.85) -> dict:
        """
        Compare deux noms avec Jaro-Winkler.
        Returns:
            {"match": bool, "score": float, "method": str}
        """
        # Normaliser
        n1 = name1.strip().lower()
        n2 = name2.strip().lower()
        
        # Exact match
        if n1 == n2:
            return {"match": True, "score": 1.0, "method": "exact"}
        
        # Jaro-Winkler (bon pour les noms propres)
        jw_score = fuzz.token_sort_ratio(n1, n2) / 100.0
        
        if jw_score >= threshold:
            return {"match": True, "score": jw_score, "method": "jaro_winkler"}
        
        # Vérifier si un nom est contenu dans l'autre
        # "Alassane Dramane Ouattara" contient "Ouattara"
        if n1 in n2 or n2 in n1:
            return {"match": True, "score": 0.75, "method": "contains"}
        
        # Vérifier le nom de famille (dernier mot)
        last1 = n1.split()[-1] if n1.split() else ""
        last2 = n2.split()[-1] if n2.split() else ""
        if last1 and last2 and last1 == last2:
            return {"match": True, "score": 0.60, "method": "same_last_name"}
        
        return {"match": False, "score": jw_score, "method": "no_match"}
    
    @staticmethod
    def find_best_match(name: str, candidates: list, threshold: float = 0.85) -> Optional[dict]:
        """Trouve le meilleur match dans une liste de candidats."""
        best = None
        best_score = 0
        
        for candidate in candidates:
            result = FuzzyNameMatcher.match(name, candidate, threshold)
            if result["match"] and result["score"] > best_score:
                best = {"candidate": candidate, **result}
                best_score = result["score"]
        
        return best
