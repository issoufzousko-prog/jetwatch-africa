import os
import json
import time
import unicodedata
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

load_dotenv()

last_poll_time = None

# Import des modules internes
from models import Base, Flight
import fetcher
import classifier
import scorer

# --- Initialisation de l'application FastAPI ---
app = FastAPI(
    title="JETWATCH AFRICA API",
    description="API pour suivre et scorer la transparence des vols présidentiels en Afrique.",
    version="1.0.0"
)

# Activation de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configuration SQLite et SQLAlchemy ---
SQLALCHEMY_DATABASE_URL = "sqlite:///./jetwatch.db"
# check_same_thread=False est nécessaire pour SQLite avec FastAPI
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Création des tables au démarrage si elles n'existent pas
Base.metadata.create_all(bind=engine)

# Dépendance pour obtenir la session de base de données
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Fonction utilitaire ---
def normaliser(texte: str) -> str:
    """Supprime les accents et met en minuscules pour comparaison."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', texte.lower())
        if unicodedata.category(c) != 'Mn'
    )

def load_flottes() -> list:
    """Charge le dictionnaire des flottes depuis le fichier JSON."""
    json_path = os.path.join(os.path.dirname(__file__), "data", "jets_africains.json")
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Erreur critique lors du chargement de {json_path}: {e}")
        return []

# --- Scheduler ---
def poll_job():
    global last_poll_time
    db = SessionLocal()
    try:
        fetcher.poll_all_fleet(db)
        last_poll_time = datetime.now()
    finally:
        db.close()

scheduler = BackgroundScheduler()
scheduler.add_job(poll_job, 'interval', minutes=60)
scheduler.start()

# --- Définition des Routes ---

@app.post("/poll")
def run_poll(db: Session = Depends(get_db)):
    """Appelle fetcher.poll_all_fleet() pour toute la flotte de tous les pays."""
    try:
        stats = fetcher.poll_all_fleet(db)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/live")
def get_live_flights(db: Session = Depends(get_db)):
    """Retourne tous les jets actuellement détectés en vol en temps réel."""
    vols = db.query(Flight).filter(Flight.arrival_time == None).all()
    result = []
    for v in vols:
        result.append({
            "icao24": v.icao24,
            "callsign": v.callsign,
            "duration_minutes": v.duration_minutes
        })
    return result

@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(Flight).count()
    classifies = db.query(Flight).filter(Flight.classification != None).count()
    non_classifies = total - classifies
    actifs = db.query(Flight).filter(Flight.arrival_time == None).count()
    
    dernier = last_poll_time.strftime("%Y-%m-%d %H:%M:%S") if last_poll_time else "Aucun"
    prochain = (last_poll_time + timedelta(minutes=60)).strftime("%Y-%m-%d %H:%M:%S") if last_poll_time else "Bientôt"
    
    return {
        "total_vols_en_base": total,
        "vols_avec_classification": classifies,
        "vols_sans_classification": non_classifies,
        "jets_actifs_detectes": actifs,
        "dernier_poll": dernier,
        "prochain_poll": prochain
    }

@app.delete("/reset-db")
def reset_db(request: Request, db: Session = Depends(get_db)):
    """Supprime tous les vols de la base de données (protégé)."""
    admin_key = request.headers.get("x-admin-key")
    if admin_key != "jetwatch2026":
        raise HTTPException(status_code=403, detail="Non autorisé")
        
    count = db.query(Flight).delete()
    db.commit()
    return {"status": "ok", "message": f"{count} vols supprimés de la base de données."}

@app.post("/classify/{pays}")
def classify_flights(pays: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Déclenche le processus de classification via Ollama en tâche de fond 
    pour tous les vols non-classifiés appartenant à la flotte du pays donné.
    """
    flottes = load_flottes()
    pays_data = next((item for item in flottes if normaliser(item["pays"]) == normaliser(pays)), None)
    
    if not pays_data:
        raise HTTPException(status_code=404, detail=f"Pays '{pays}' inconnu.")
        
    background_tasks.add_task(classifier.batch_classify, db, pays_data["pays"])
        
    return {"status": "classification_en_cours", "pays": pays_data["pays"]}

@app.get("/score/{pays}")
def get_score(pays: str, db: Session = Depends(get_db)):
    """
    Retourne le calcul détaillé du score de transparence, l'empreinte carbone
    et les métriques d'utilisation pour le dirigeant du pays donné.
    """
    flottes = load_flottes()
    pays_data = next((item for item in flottes if normaliser(item["pays"]) == normaliser(pays)), None)
    
    if not pays_data:
        raise HTTPException(status_code=404, detail=f"Pays '{pays}' inconnu.")
        
    try:
        result = scorer.score_president(pays_data["pays"], db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur interne lors du scoring: {e}")
        
    if not result:
        # Signifie qu'il n'y a aucun vol en base pour ce pays
        raise HTTPException(status_code=404, detail=f"Aucun vol enregistré pour le pays '{pays_data['pays']}'. Impossible de générer un score.")
        
    return result

@app.get("/classement")
def get_classement(db: Session = Depends(get_db)):
    flottes = load_flottes()
    classement = []
    
    for item in flottes:
        pays_nom = item["pays"]
        dirigeant = item["dirigeant"]
        flotte = item.get("flotte", [])
        
        jets_verifies = sum(1 for j in flotte if j.get("verifie") is True)
        if jets_verifies == 0:
            continue
            
        try:
            result = scorer.score_president(pays_nom, db)
            if result and result.get("total_vols", 0) > 0:
                classement.append({
                    "pays": result.get("pays"),
                    "dirigeant": result.get("dirigeant"),
                    "score_global": result.get("score_global"),
                    "niveau": result.get("niveau"),
                    "total_vols": result.get("total_vols"),
                    "co2_kg": result.get("co2_kg"),
                    "jets_verifies": jets_verifies,
                    "statut": "données disponibles"
                })
            else:
                classement.append({
                    "pays": pays_nom,
                    "dirigeant": dirigeant,
                    "score_global": 0,
                    "niveau": "N/A",
                    "total_vols": 0,
                    "co2_kg": 0,
                    "jets_verifies": jets_verifies,
                    "statut": "en attente de détection"
                })
        except Exception as e:
            continue
            
    classement_vols = sorted([c for c in classement if c["total_vols"] > 0], key=lambda x: x["score_global"], reverse=True)
    classement_sans_vols = sorted([c for c in classement if c["total_vols"] == 0], key=lambda x: x["jets_verifies"], reverse=True)
    
    result = classement_vols + classement_sans_vols
    return result[:30]

@app.get("/health")
def health_check():
    """
    Route de contrôle de santé du service.
    """
    return {"status": "ok", "version": "1.0.0"}

@app.get("/pays")
def get_pays():
    """Retourne la liste triée des pays avec leurs dirigeants."""
    flottes = load_flottes()
    result = []
    for item in flottes:
        flotte = item.get("flotte", [])
        jets_verifies = sum(1 for j in flotte if j.get("verifie") is True)
        result.append({
            "pays": item["pays"],
            "dirigeant": item["dirigeant"],
            "type_regime": item.get("type_regime", "Inconnu"),
            "jets_verifies": jets_verifies
        })
    result.sort(key=lambda x: normaliser(x["pays"]))
    return result

@app.get("/vols/{pays}")
def get_vols_pays(pays: str, db: Session = Depends(get_db)):
    """Retourne tous les vols du pays avec les informations enrichies (tail_number)."""
    flottes = load_flottes()
    pays_data = next((item for item in flottes if normaliser(item["pays"]) == normaliser(pays)), None)
    
    if not pays_data:
        raise HTTPException(status_code=404, detail=f"Pays '{pays}' inconnu.")
        
    icao24_map = {jet["icao24"].lower(): jet.get("tail_number", "Inconnu") 
                  for jet in pays_data.get("flotte", []) if jet.get("icao24")}
                  
    if not icao24_map:
        return []
        
    icao_list = list(icao24_map.keys())
    
    # Récupérer les vols et les trier par date décroissante
    vols = db.query(Flight).filter(Flight.icao24.in_(icao_list)).order_by(Flight.departure_time.desc()).all()
    
    result = []
    for v in vols:
        result.append({
            "id": v.id,
            "icao24": v.icao24,
            "tail_number": icao24_map.get(v.icao24.lower(), "Inconnu"),
            "callsign": v.callsign,
            "departure_airport": v.departure_airport,
            "arrival_airport": v.arrival_airport,
            "departure_time": v.departure_time,
            "duration_minutes": v.duration_minutes,
            "classification": v.classification,
            "co2_kg": v.co2_kg
        })
        
    return result

@app.get("/airport/{icao}")
def get_airport(icao: str):
    """Retourne les coordonnées depuis airports.json"""
    json_path = os.path.join(os.path.dirname(__file__), "data", "airports.json")
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            airports = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Erreur interne (dictionnaire des aéroports introuvable).")
        
    airport_data = airports.get(icao.upper())
    if not airport_data:
        raise HTTPException(status_code=404, detail=f"Aéroport {icao} non trouvé.")
        
    return airport_data
