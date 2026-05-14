"""
JetWatch Africa — Couches 3 + 4 : OSINT & Graphe Relationnel

Ce module orchestre la partie purement Python du pipeline d'investigation :
- Couche 3 : Collecte OSINT (via investigator_osint)
- Couche 4 : Graphe relationnel & Dijkstra (via investigator_graph)

Les couches 2 (Classification LLM) et 5 (Rapport Détective) sont entièrement
gérées par l'instance WebLLM (WebGPU) dans le navigateur. Ce module expose
les fonctions `build_classification_prompt`, `build_graph_prompt` et
`build_detective_prompt` pour que le backend puisse les pré-construire et
les envoyer au frontend, qui les soumet au moteur Llama 3 local.
"""

import os
import json
import unicodedata
from datetime import datetime
from sqlalchemy.orm import Session
from models import Flight

import investigator_osint
import investigator_graph


def normaliser(texte: str) -> str:
    """Supprime les accents et met en minuscules pour comparaison."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', texte.lower())
        if unicodedata.category(c) != 'Mn'
    )


# ═══════════════════════════════════════════════════════════════════════
# COUCHE 2 — PROMPT DE CLASSIFICATION (construit côté backend, exécuté
#             par WebLLM dans le navigateur)
# ═══════════════════════════════════════════════════════════════════════

def build_classification_prompt(vol: Flight, context: dict) -> str:
    """
    Construit le prompt de classification Couche 2.
    Ce prompt est envoyé au frontend qui le soumet à Llama 3 via WebGPU.
    Retourne un str (prompt complet).
    """
    if vol.departure_time:
        dt = datetime.fromtimestamp(vol.departure_time)
        jours_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        jour_semaine = jours_fr[dt.weekday()]
        heure_locale = dt.strftime("%H:%M")
        date_vol = dt.strftime("%Y-%m-%d")
    else:
        jour_semaine = "Inconnu"
        heure_locale = "Inconnue"
        date_vol = "Inconnue"

    pays = context.get("pays", "Inconnu")
    dep = vol.departure_airport or "Inconnu"
    arr = vol.arrival_airport or "Inconnu"
    duree = vol.duration_minutes or 0

    return f"""Tu es un analyste spécialisé en transparence politique et audit des vols d'État.
Ta tâche est de classifier un vol de jet d'État dans EXACTEMENT UNE catégorie :
"diplomatique", "officiel" ou "personnel".

---

## DONNÉES DU VOL
- Pays du dirigeant    : {pays}
- Aéroport de départ  : {dep} (IATA)
- Aéroport d'arrivée  : {arr} (IATA)
- Durée du vol        : {duree} minutes
- Date du vol         : {date_vol}
- Jour de la semaine  : {jour_semaine}
- Heure de départ (locale) : {heure_locale}
- Source du tracking  : ADS-B

---

## PROTOCOLE DE CLASSIFICATION EN 3 ÉTAPES

### ÉTAPE 1 — Analyse contextuelle primaire
Avant toute classification, réponds mentalement à ces questions :
1. La destination est-elle une capitale nationale ou étrangère ?
2. Y avait-il un événement officiel connu à cette date/destination ?
3. Le profil temporel est-il suspect ?
   - Départ vendredi soir / retour lundi matin → signal personnel fort
   - Durée < 90 min pour un vol international → vol de positionnement technique
   - Séjour < 6h sur place → escale technique ou réunion express

### ÉTAPE 2 — Vérification externe obligatoire
Si la destination est une ville à double usage (Paris, Genève, Dubai, Nice,
Bruxelles, New York, Monaco, Dubaï, Doha, Istanbul, Abidjan, etc.)
tu DOIS rechercher :
- Les agendas officiels publiés du dirigeant à cette date
- Les sommets, réunions, conférences prévus (UA, ONU, G20, COP, CEDEAO, etc.)

### ÉTAPE 3 — Matrice de décision finale

A) DIPLOMATIQUE si :
   - La destination est une capitale étrangère ET un événement officiel est confirmé
   - OU la destination est le siège d'une organisation internationale

B) OFFICIEL si :
   - La destination est dans le même pays (vol intérieur)
   - OU c'est un vol de positionnement technique (durée < 90 min, retour rapide)

C) PERSONNEL si :
   - Aucun événement officiel identifiable à la destination à cette date
   - ET le profil temporel coïncide avec un week-end ou congé
   - ET la destination est connue pour le tourisme de luxe ou le séjour d'agrément

RÈGLE DE DÉPARTAGE : En cas de doute entre "diplomatique" et "personnel"
pour une destination ambiguë (Paris, Dubai, Genève), PERSONNEL est la
classification par défaut sauf preuve contraire documentée.

---

## FORMAT DE RÉPONSE OBLIGATOIRE

Réponds UNIQUEMENT avec ce bloc JSON, sans aucun texte avant ou après :

{{
  "classification": "<diplomatique|officiel|personnel>",
  "confiance": "<haute|moyenne|faible>",
  "evenement_confirme": "<description de l'événement officiel trouvé, ou 'aucun'>",
  "sources_consultees": ["<url ou nom de source 1>", "..."],
  "signal_alerte": "<oui|non>",
  "motif_alerte": "<raison si signal_alerte=oui, sinon null>"
}}"""


# ═══════════════════════════════════════════════════════════════════════
# COUCHE 4a — PROMPT DE GRAPHE (construit côté backend, exécuté par WebLLM)
# ═══════════════════════════════════════════════════════════════════════

def build_graph_prompt(dirigeant: str, pays: str, destination: str,
                       date_vol: str, osint_data: dict) -> str:
    """Construit le prompt pour que le LLM (WebGPU) génère le graphe relationnel."""
    press_summary = ""
    for item in osint_data.get("press", [])[:5]:
        press_summary += f"- {item['title']}: {item['body'][:100]}\n"

    family_summary = ""
    for item in osint_data.get("family_tree", [])[:8]:
        family_summary += f"- {item['title']}: {item['body'][:100]}\n"

    assets_summary = ""
    for item in osint_data.get("assets_at_destination", [])[:5]:
        assets_summary += f"- [{item.get('person','')}] {item['title']}: {item['body'][:100]}\n"

    offshore_summary = ""
    for item in osint_data.get("offshore_leaks", [])[:5]:
        offshore_summary += f"- [{item.get('person','')}] {item['title']}: {item['body'][:100]}\n"

    return f"""Tu es un enquêteur spécialisé en investigation patrimoniale.
À partir des données OSINT suivantes, construis un graphe relationnel JSON
reliant le dirigeant à ses proches et aux actifs étrangers identifiés.

DIRIGEANT : {dirigeant} — {pays}
DESTINATION : {destination}
DATE : {date_vol}

═══ DONNÉES OSINT COLLECTÉES ═══

PRESSE :
{press_summary if press_summary else "Aucun résultat"}

FAMILLE & ENTOURAGE :
{family_summary if family_summary else "Aucun résultat"}

ACTIFS À DESTINATION :
{assets_summary if assets_summary else "Aucun résultat"}

OFFSHORE / ENQUÊTES :
{offshore_summary if offshore_summary else "Aucun résultat"}

═══ FORMAT DE SORTIE OBLIGATOIRE ═══

Retourne UNIQUEMENT un JSON avec cette structure exacte :

{{
  "nodes": [
    {{"id": "dirigeant", "name": "{dirigeant}", "category": "racine", "degree": 0, "details": {{"fonction": "Président"}}}},
    {{"id": "epouse", "name": "NOM TROUVÉ", "category": "famille", "degree": 1, "details": {{"relation": "conjoint"}}}},
    {{"id": "actif_1", "name": "Villa/Appart/SCI...", "category": "actif_etranger", "degree": 4, "details": {{"adresse": "...", "valeur_estimee": "..."}}}}
  ],
  "edges": [
    {{"source": "dirigeant", "target": "epouse", "relation": "conjoint_de", "weight": 1, "source_evidence": "Source publique", "evidence_type": "officiel"}},
    {{"source": "epouse", "target": "actif_1", "relation": "propriétaire_de", "weight": 2, "source_evidence": "...", "evidence_type": "presse"}}
  ]
}}

RÈGLES :
- N'inclus que les nœuds pour lesquels tu as trouvé un NOM dans les données OSINT.
- Poids 1 = lien documenté avec source, Poids 2 = recoupement, Poids 3 = supposé.
- TOUJOURS inclure le nœud "dirigeant" comme racine.
- Retourne UNIQUEMENT le JSON, pas de texte avant ni après."""


# ═══════════════════════════════════════════════════════════════════════
# COUCHE 5 — PROMPT DU RAPPORT DÉTECTIVE (construit côté backend,
#             exécuté par WebLLM dans le navigateur)
# ═══════════════════════════════════════════════════════════════════════

def build_detective_prompt(dirigeant: str, pays: str, destination: str,
                            date_vol: str, duree_sejour: str,
                            graph_results: dict, osint_data: dict) -> str:
    """Construit le prompt du rapport détective final pour WebLLM."""
    chains_text = ""
    if graph_results.get("formatted_chains"):
        for i, chain in enumerate(graph_results["formatted_chains"], 1):
            chains_text += f"\nCHAÎNE {i}:\n{chain}\n"
    else:
        chains_text = "Aucune chaîne de connexion trouvée."

    stats = graph_results.get("stats", {})
    risk = graph_results.get("risk_indicators", {})

    return f"""Tu es un détective privé spécialisé en investigation patrimoniale et transparence
politique. Un vol de jet d'État vient d'être classifié "personnel".

Ta mission : produire un dossier d'enquête complet en remontant la chaîne des
propriétaires jusqu'au dirigeant, en utilisant UNIQUEMENT des sources publiques.

═══════════════════════════════════════════════════════
DONNÉES D'ENTRÉE
═══════════════════════════════════════════════════════
- Dirigeant         : {dirigeant} — {pays}
- Destination       : {destination}
- Date du vol       : {date_vol}
- Durée du séjour   : {duree_sejour}
- Classification    : PERSONNEL (confirmée)

═══════════════════════════════════════════════════════
RÉSULTATS DU GRAPHE RELATIONNEL (Dijkstra)
═══════════════════════════════════════════════════════
Nœuds trouvés : {stats.get('total_nodes', 0)}
Liens trouvés : {stats.get('total_edges', 0)}
Liens documentés : {stats.get('edges_documented', 0)}
Actifs identifiés : {risk.get('nb_actifs_trouves', 0)}

CHAÎNES DE CONNEXION IDENTIFIÉES :
{chains_text}

═══════════════════════════════════════════════════════
DONNÉES OSINT BRUTES DISPONIBLES
═══════════════════════════════════════════════════════
Résultats presse : {len(osint_data.get('press', []))}
Résultats famille : {len(osint_data.get('family_tree', []))}
Résultats actifs : {len(osint_data.get('assets_at_destination', []))}
Résultats offshore : {len(osint_data.get('offshore_leaks', []))}

═══════════════════════════════════════════════════════
INSTRUCTIONS
═══════════════════════════════════════════════════════
Produis un rapport structuré ainsi :

### 🔍 RÉSUMÉ EXÉCUTIF (3-5 phrases)
### 📊 SCORE DE RISQUE (transparence, cohérence agendas, degré dissimulation)
### 🌳 GRAPHE RELATIONNEL CONSTRUIT
### 🔗 CHAÎNES DE CONNEXION (chemin le plus court)
### 🗂️ SOURCES CONSULTÉES
### ⚠️ LIMITES DE L'ENQUÊTE
### 📋 PROCHAINES ÉTAPES RECOMMANDÉES

═══════════════════════════════════════════════════════
RÈGLES IMPÉRATIVES
═══════════════════════════════════════════════════════
✓ Ne cite JAMAIS un actif sans source publique vérifiable
✓ Distingue toujours "documenté" vs "supposé"
✓ N'accuse pas directement — présente des faits et liens
✓ Mentionne explicitement les données manquantes"""


# ═══════════════════════════════════════════════════════════════════════
# COUCHES 3 + 4 — PIPELINE PYTHON PUR (sans LLM)
# ═══════════════════════════════════════════════════════════════════════

def prepare_investigation_data(vol: Flight, context: dict) -> dict:
    """
    Exécute les couches 3 et 4 du pipeline sans aucun appel LLM.
    - Couche 3 : Collecte OSINT (investigator_osint)
    - Couche 4 : Algorithme de Dijkstra (investigator_graph)

    Retourne toutes les données brutes + les prompts pré-construits
    que le frontend soumettra à WebLLM pour générer :
    - Le graphe relationnel (Couche 4a via LLM)
    - Le rapport détective final (Couche 5)
    """
    dirigeant = context.get("dirigeant", "Inconnu")
    pays = context.get("pays", "Inconnu")
    destination = vol.arrival_airport or "Inconnu"
    date_vol = "Inconnue"
    duree_sejour = "Inconnue"

    if vol.departure_time:
        dt = datetime.fromtimestamp(vol.departure_time)
        date_vol = dt.strftime("%Y-%m-%d")

    if vol.departure_time and vol.arrival_time:
        duree_h = (vol.arrival_time - vol.departure_time) / 3600
        duree_sejour = f"{round(duree_h, 1)} heures"

    print(f"\n{'='*60}")
    print(f"[COUCHE 3+4] Démarrage pour {dirigeant} → {destination}")
    print(f"{'='*60}")

    # ── COUCHE 3 : Collecte OSINT (Python pur) ──
    print("\n[COUCHE 3] Collecte OSINT en cours...")
    osint_data = investigator_osint.gather_all_osint(
        dirigeant=dirigeant,
        pays=pays,
        destination=destination,
        date_vol=date_vol,
        noms_reseau=[dirigeant]
    )

    # ── COUCHE 4b : Dijkstra sur graphe minimal (Python pur) ──
    # Le graphe complet sera construit par le LLM (WebGPU) côté frontend,
    # mais on lance Dijkstra sur un graphe structurel de base pour initialiser.
    print("\n[COUCHE 4] Initialisation du graphe minimal + Dijkstra...")
    graph_json_minimal = {
        "nodes": [
            {"id": "dirigeant", "name": dirigeant, "category": "racine",
             "degree": 0, "details": {"pays": pays}}
        ],
        "edges": []
    }
    graph_results = investigator_graph.run_investigation_graph(
        "dirigeant", graph_json_minimal
    )

    nb_paths = len(graph_results.get("paths", {}))
    print(f"[COUCHE 4] Graphe minimal initialisé. {nb_paths} chemin(s) calculé(s).")
    print(f"{'='*60}\n")

    # Construire les prompts pour le frontend
    graph_prompt = build_graph_prompt(
        dirigeant, pays, destination, date_vol, osint_data
    )
    detective_prompt = build_detective_prompt(
        dirigeant, pays, destination, date_vol, duree_sejour,
        graph_results, osint_data
    )

    return {
        "osint_data": osint_data,
        "graph_results": graph_results,
        "graph_prompt": graph_prompt,
        "detective_prompt": detective_prompt,
        "meta": {
            "dirigeant": dirigeant,
            "pays": pays,
            "destination": destination,
            "date_vol": date_vol,
            "duree_sejour": duree_sejour
        }
    }
