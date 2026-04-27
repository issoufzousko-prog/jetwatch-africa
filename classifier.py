import os
import json
import requests
import unicodedata
from datetime import datetime
from sqlalchemy.orm import Session
from models import Flight

OLLAMA_MODEL = "mistral"  # Peut être changé en "llama3" selon vos besoins
OLLAMA_API_URL = "http://localhost:11434/api/generate"

def normaliser(texte: str) -> str:
    """Supprime les accents et met en minuscules pour comparaison."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', texte.lower())
        if unicodedata.category(c) != 'Mn'
    )

def classify_flight(vol: Flight, context: dict) -> str:
    """
    Classifie un vol en interrogeant une instance locale d'Ollama.
    Catégories possibles : "diplomatique", "officiel", "personnel".
    """
    # 1. Préparation des données temporelles
    if vol.departure_time:
        dt = datetime.fromtimestamp(vol.departure_time)
        jours_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        jour_semaine = jours_fr[dt.weekday()]
        heure_locale = dt.strftime("%H:%M")
    else:
        jour_semaine = "Inconnu"
        heure_locale = "Inconnue"

    pays = context.get("pays", "Inconnu")
    dep = vol.departure_airport or "Inconnu"
    arr = vol.arrival_airport or "Inconnu"
    duree = vol.duration_minutes or 0

    # 2. Construction du prompt pour Ollama
    prompt = f"""Tu es un expert en analyse de vols d'État et de transparence politique.
Analyse le vol suivant d'un jet d'État et classifie-le dans EXACTEMENT UNE de ces trois catégories : "diplomatique", "officiel" ou "personnel".

Informations sur le vol :
- Pays du dirigeant : {pays}
- Aéroport de départ : {dep}
- Aéroport d'arrivée : {arr}
- Durée du vol : {duree} minutes
- Jour de la semaine : {jour_semaine}
- Heure de départ locale : {heure_locale}

Règles de classification STRICTES :
- "diplomatique" : La destination est une capitale étrangère ou le siège d'une organisation internationale (ONU, UA, UE, etc.).
- "officiel" : La destination est nationale (dans le même pays) ou c'est un vol de positionnement technique court.
- "personnel" : La destination est touristique (resort, week-end, vacances) ou vers des destinations d'agrément connues comme Dubai, Paris, Genève, Nice, Monaco, etc.

Retourne UNIQUEMENT le mot de la catégorie choisie en minuscules, sans aucune ponctuation, sans explication ni texte supplémentaire.
"""

    # 3. Appel à Ollama via HTTP local (stream: false)
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        raw_answer = data.get("response", "").strip().lower()
    except Exception as e:
        print(f"Erreur lors de l'appel à Ollama: {e}")
        raw_answer = ""

    # 4. Parsing robuste de la réponse
    if "diplomatique" in raw_answer:
        return "diplomatique"
    elif "personnel" in raw_answer:
        return "personnel"
    else:
        # En cas de réponse ambiguë ou d'échec de la requête, on est conservateur
        return "officiel"


def batch_classify(db: Session, pays: str) -> None:
    """
    Classifie tous les vols non-classifiés d'un pays donné et met à jour la base de données.
    Affiche la progression dans le terminal.
    """
    json_path = os.path.join(os.path.dirname(__file__), "data", "jets_africains.json")
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            flottes = json.load(f)
    except Exception as e:
        print(f"Erreur lors du chargement de {json_path}: {e}")
        return

    # Recherche des données du pays
    pays_data = next((item for item in flottes if normaliser(item["pays"]) == normaliser(pays)), None)
            
    if not pays_data:
        print(f"Pays '{pays}' introuvable dans le fichier JSON.")
        return
        
    icao24_list = [jet["icao24"].lower() for jet in pays_data.get("flotte", []) if jet.get("icao24")]
    
    if not icao24_list:
        print(f"Aucun code ICAO24 défini (ou vérifié) pour la flotte de {pays}.")
        return

    # Sélection des vols sans classification (classification IS NULL)
    vols_non_classes = db.query(Flight).filter(
        Flight.icao24.in_(icao24_list),
        Flight.classification == None
    ).all()

    total = len(vols_non_classes)
    if total == 0:
        print(f"✅ Tous les vols enregistrés pour {pays} sont déjà classifiés.")
        return

    print(f"Début de la classification LLM pour {pays} ({total} vols non classifiés)...")
    
    context = {"pays": pays_data["pays"]}
    count = 0

    for vol in vols_non_classes:
        count += 1
        classe = classify_flight(vol, context)
        vol.classification = classe
        print(f"[{count}/{total}] Vol {vol.icao24} ({vol.departure_airport} → {vol.arrival_airport}) => {classe.upper()}")
        
        # Commit à chaque étape (sauvegarde continue en cas de plantage d'Ollama)
        db.commit()

    print(f"🎉 Classification terminée. {count} vols mis à jour.")
