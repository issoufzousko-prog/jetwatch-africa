import os
import json
import time
import csv
import re
import unicodedata
from duckduckgo_search import DDGS
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
# Import des modules internes
from database import SessionLocal, engine, get_db
from models import Flight, User, Target, TargetFleet
from utils import normaliser, load_flottes

import fetcher
import classifier
import scorer
import security
import ec_pow
import ec_ecdh
from jet_osint import find_vip_jet
from fastapi import Body
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from fastapi.responses import RedirectResponse

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# --- Initialisation de l'application FastAPI ---
app = FastAPI(
    title="JETWATCH AFRICA API",
    description="API pour suivre et scorer la transparence des vols présidentiels en Afrique.",
    version="1.0.0"
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Activation de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://127.0.0.1:5173", 
        "http://localhost:4173",
        "https://jetwatch-africa.com",
        "https://jetwatch-africa.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "super-secret-jetwatch-key-2026-ecc"))

# ─────────────────────────────────────────────────────────────────────
# EC PROOF-OF-WORK MIDDLEWARE
# ─────────────────────────────────────────────────────────────────────

# Routes exemptées du PoW (bootstrap nécessaire pour obtenir un challenge)
_POW_EXEMPT_PREFIXES = [
    "/pow/challenge",
    "/ecdh/handshake",
    "/health",
    "/auth/",
    "/api/auth/",
    "/api/users",
    "/proxy-image",
    "/pays",
    "/docs",
    "/openapi",
    "/redoc",
]

class ECPoWMiddleware(BaseHTTPMiddleware):
    """
    Middleware de pare-feu EC Proof-of-Work.

    Vérifie les headers X-PoW-Challenge-Id et X-PoW-Nonce sur toutes
    les requêtes non-exemptées. Bloque silencieusement les bots qui
    ne peuvent pas résoudre le challenge EC mathématique.
    """
    async def dispatch(self, request, call_next):
        path = request.url.path

        # Exempter les routes de bootstrap
        for prefix in _POW_EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Exempter les OPTIONS (preflight CORS)
        if request.method == "OPTIONS":
            return await call_next(request)

        challenge_id = request.headers.get("X-PoW-Challenge-Id", "")
        nonce_str = request.headers.get("X-PoW-Nonce", "")

        if not challenge_id or not nonce_str:
            stats = ec_pow.get_stats()
            return JSONResponse(
                status_code=429,
                content={
                    "error": "pow_required",
                    "message": "Preuve de travail requise. Obtenez un défi sur GET /pow/challenge",
                    "difficulty": stats["current_difficulty"]
                },
                headers={"Retry-After": "1"}
            )

        try:
            nonce = int(nonce_str)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"error": "pow_invalid", "message": "Nonce invalide (doit être un entier)"}
            )

        valid, reason = ec_pow.verify_pow(challenge_id, nonce)
        if not valid:
            return JSONResponse(
                status_code=403,
                content={"error": "pow_failed", "message": f"PoW invalide: {reason}"}
            )

        return await call_next(request)

app.add_middleware(ECPoWMiddleware)

# ─────────────────────────────────────────────────────────────────────
# EC-POW ENDPOINTS
# ─────────────────────────────────────────────────────────────────────

@app.get("/pow/challenge")
def get_pow_challenge():
    """
    Retourne un nouveau défi EC Proof-of-Work.
    Cette route est exemptée du PoW (route de bootstrap).

    Le client doit trouver un nonce tel que :
      SHA256(point_x_bytes || point_y_bytes || nonce_bytes)
    commence par `difficulty` bits à zéro.
    """
    return ec_pow.generate_challenge()

@app.get("/pow/stats")
def get_pow_stats():
    """Monitoring du pare-feu PoW (état de l'attaque, difficulté actuelle)."""
    return {
        "pow": ec_pow.get_stats(),
        "ecdh": ec_ecdh.get_session_stats()
    }

# ─────────────────────────────────────────────────────────────────────
# ECDH SESSION ENDPOINTS
# ─────────────────────────────────────────────────────────────────────

class ECDHHandshakeRequest(BaseModel):
    client_public_key_pem: str

@app.post("/ecdh/handshake")
def ecdh_handshake(payload: ECDHHandshakeRequest):
    """
    Effectue l'échange de clé Diffie-Hellman sur courbe elliptique.
    Cette route est exemptée du PoW (elle s'exécute avant le challenge).

    Protocole :
    1. Client génère sa paire ECDH éphémère (P-256)
    2. Client envoie client_public_key_pem
    3. Serveur génère sa paire éphémère, calcule ECDH, dérive AES-256 via HKDF
    4. Retourne server_public_key_pem + session_id
    5. Client calcule la même clé AES-256 de son côté
    → Clé partagée établie sans jamais la transmettre (Forward Secrecy)
    """
    try:
        result = ec_ecdh.ecdh_handshake(payload.client_public_key_pem)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# OAuth Setup
oauth = OAuth()
oauth.register(
    name='github',
    client_id=os.getenv("GITHUB_CLIENT_ID", ""),
    client_secret=os.getenv("GITHUB_CLIENT_SECRET", ""),
    access_token_url='https://github.com/login/oauth/access_token',
    access_token_params=None,
    authorize_url='https://github.com/login/oauth/authorize',
    authorize_params=None,
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email', 'timeout': 60.0},
)

oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
    client_kwargs={'scope': 'openid email profile', 'timeout': 60.0},
)

# Sécurité par API Key
from fastapi.security import APIKeyHeader
API_KEY_NAME = "X-Jetwatch-Api-Key"
API_KEY = os.getenv("JETWATCH_API_KEY", "jetwatch-local-secure-key-2026")
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Accès refusé : Clé API invalide")
    return api_key

# --- Configuration SQLite et SQLAlchemy ---
# La configuration de la base de données a été déplacée dans database.py


# Création des tables au démarrage si elles n'existent pas
# Créer les tables si nécessaire
import models
models.Base.metadata.create_all(bind=engine)


def init_db_from_json():
    db = SessionLocal()
    try:
        json_path = os.path.join(os.path.dirname(__file__), "data", "jets_africains.json")
        if not os.path.exists(json_path):
            return
            
        with open(json_path, 'r', encoding='utf-8') as f:
            flottes = json.load(f)
            
        added = 0
        for item in flottes:
            pays_nom = item.get("pays")
            if not pays_nom:
                continue
                
            existing = db.query(Target).filter(Target.pays == pays_nom).first()
            if existing:
                continue
                
            target = Target(
                pays=pays_nom,
                dirigeant=item.get("dirigeant"),
                type_regime=item.get("type_regime"),
                photo_url=item.get("photo_url")
            )
            db.add(target)
            db.commit()
            db.refresh(target)
            
            for jet in item.get("flotte", []):
                fleet_item = TargetFleet(
                    target_id=target.id,
                    icao24=jet.get("icao24", "").lower() if jet.get("icao24") else "",
                    tail_number=jet.get("tail_number"),
                    description=jet.get("description"),
                    verifie=jet.get("verifie", True)
                )
                db.add(fleet_item)
            db.commit()
            added += 1
            
        if added > 0:
            print(f"Migration JSON vers SQL réussie: {added} cibles ajoutées.")
    except Exception as e:
        print(f"Erreur de migration: {e}")
    finally:
        db.close()

@app.on_event("startup")
def on_startup():
    init_db_from_json()


# Dépendance pour obtenir la session de base de données
# get_db est maintenant importé de database.py


# Fin des utilitaires


# --- Vercel Cron Endpoints ---
from fastapi import Header

def verify_cron_secret(authorization: str = Header(None)):
    """Sécurité pour les requêtes Vercel Cron."""
    cron_secret = os.getenv("CRON_SECRET")
    if cron_secret and authorization != f"Bearer {cron_secret}":
        raise HTTPException(status_code=401, detail="Non autorisé")
    return True

@app.post("/api/cron/poll")
@app.get("/api/cron/poll") # Support GET for simple cron pings
def cron_poll(db: Session = Depends(get_db), _auth=Depends(verify_cron_secret)):
    """Tâche Cron : Polling de la flotte (ex: toutes les 5 mins)."""
    global last_poll_time
    try:
        stats = fetcher.poll_all_fleet(db)
        last_poll_time = datetime.now()
        return {"status": "ok", "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cron/clean")
@app.get("/api/cron/clean")
def cron_clean(db: Session = Depends(get_db), _auth=Depends(verify_cron_secret)):
    """Tâche Cron : Nettoyage des anciennes trajectoires (>48h)."""
    try:
        from models import FlightPosition
        cutoff_time = int(time.time()) - 172800 # 48h en secondes
        count = db.query(FlightPosition).filter(FlightPosition.timestamp < cutoff_time).delete()
        db.commit()
        return {"status": "ok", "deleted": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import social_bot

@app.post("/api/cron/daily-post")
@app.get("/api/cron/daily-post")
def cron_daily_post(_auth=Depends(verify_cron_secret)):
    """Tâche Cron : Publication sur les réseaux sociaux (ex: tous les jours à 18h)."""
    try:
        social_bot.run_daily_post()
        return {"status": "ok", "message": "Bot social exécuté avec succès."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Définition des Routes ---

@app.get("/api/users/count")
def get_users_count(db: Session = Depends(get_db)):
    count = db.query(User).count()
    return {"count": count}


@app.get("/api/auth/login/{provider}")
async def login(request: Request, provider: str, db: Session = Depends(get_db)):
    client = oauth.create_client(provider)
    if not client:
        raise HTTPException(status_code=404, detail="Provider not found")
    redirect_uri = str(request.url_for('auth_callback', provider=provider))
    # Replace 127.0.0.1 with localhost to match Google Console config
    redirect_uri = redirect_uri.replace("127.0.0.1", "localhost")
    if not redirect_uri.startswith("http://localhost"):
        redirect_uri = redirect_uri.replace("http://", "https://")
    return await client.authorize_redirect(request, redirect_uri)

@app.get("/api/auth/callback/{provider}")
async def auth_callback(request: Request, provider: str, db: Session = Depends(get_db)):
    client = oauth.create_client(provider)
    if not client:
        raise HTTPException(status_code=404, detail="Provider not found")
        
    try:
        token = await client.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    user_info = None
    if provider == 'google':
        user_info = token.get('userinfo')
    elif provider == 'github':
        resp = await client.get('user', token=token)
        user_info = resp.json()
        
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to fetch user info")
        
    provider_id = str(user_info.get("sub") or user_info.get("id"))
    email = user_info.get("email")
    name = user_info.get("name") or user_info.get("login")
    avatar_url = user_info.get("picture") or user_info.get("avatar_url")
    
    user = db.query(User).filter(User.provider_id == provider_id, User.provider == provider).first()
    if not user:
        user = User(
            provider=provider,
            provider_id=provider_id,
            email=email,
            name=name,
            avatar_url=avatar_url,
            last_login=int(time.time())
        )
        db.add(user)
    else:
        user.last_login = int(time.time())
        user.avatar_url = avatar_url
        user.name = name
        
    db.commit()
    db.refresh(user)
    
    access_token = security.create_access_token(data={"sub": user.id})
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    return RedirectResponse(url=f"{frontend_url}/?token={access_token}")

@app.get("/api/users")
def get_public_users(db: Session = Depends(get_db)):
    users = db.query(User).filter(User.is_active == True).order_by(User.last_login.desc()).all()
    return [{"id": u.id, "name": u.name, "avatar_url": u.avatar_url, "provider": u.provider} for u in users]

def get_current_user_dep(request: Request, db: Session = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth_header.split(" ")[1]
    payload = security.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.get("/api/users/me")
def get_current_user(user: User = Depends(get_current_user_dep)):
    return {"id": user.id, "name": user.name, "email": user.email, "avatar_url": user.avatar_url, "provider": user.provider, "role": user.role}

def get_admin_user(user: User = Depends(get_current_user_dep)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Privilèges administrateur requis.")
    return user

def require_auth(request: Request, db: Session = Depends(get_db)):
    """Dependency that requires a valid JWT token. Returns the user or raises 401."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentification requise. Veuillez vous connecter.")
    token = auth_header.split(" ")[1]
    payload = security.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré.")
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable.")
    return user

@app.post("/poll")
def run_poll(db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """Appelle fetcher.poll_all_fleet() pour toute la flotte de tous les pays."""
    try:
        stats = fetcher.poll_all_fleet(db)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/live/trajectories")
def get_live_trajectories(db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """Retourne tous les jets actuellement en vol avec leur trajectoire, position actuelle, et pays."""
    vols = db.query(Flight).filter(Flight.arrival_time == None).all()
    
    flottes = load_flottes()
    icao_to_pays = {}
    icao_to_tail = {}
    icao_to_dirigeant = {}
    for item in flottes:
        for jet in item.get("flotte", []):
            if jet.get("icao24"):
                icao = jet["icao24"].lower()
                icao_to_pays[icao] = item["pays"]
                icao_to_tail[icao] = jet.get("tail_number", "Inconnu")
                icao_to_dirigeant[icao] = item.get("dirigeant", "Inconnu")
                
    result = []
    for v in vols:
        icao = v.icao24.lower()
        pays = icao_to_pays.get(icao, "Inconnu")
        tail = icao_to_tail.get(icao, "Inconnu")
        dirigeant = icao_to_dirigeant.get(icao, "Inconnu")
        
        # Récupérer l'historique des positions ordonné par timestamp
        positions = sorted(v.positions, key=lambda p: p.timestamp)
        path = [[p.lat, p.lon] for p in positions]
        
        current_pos = None
        current_track = 0
        if positions:
            last_p = positions[-1]
            current_pos = [last_p.lat, last_p.lon]
            current_track = last_p.track if last_p.track is not None else 0
            
        # N'inclure que si on a au moins une position
        if current_pos:
            result.append({
                "id": v.id,
                "icao24": v.icao24,
                "tail_number": tail,
                "pays": pays,
                "dirigeant": dirigeant,
                "callsign": v.callsign,
                "duration_minutes": v.duration_minutes,
                "current_pos": current_pos,
                "current_track": current_track,
                "path": path
            })
    return result

@app.get("/live/predictions/{icao24}")
def get_flight_predictions(icao24: str, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """Retourne les prédictions de destination basées sur le cône de projection."""
    vol = db.query(Flight).filter(Flight.icao24 == icao24.lower(), Flight.arrival_time == None).order_by(Flight.departure_time.desc()).first()
    
    if not vol or not vol.positions:
        return {"predictions": []}
        
    last_pos = sorted(vol.positions, key=lambda p: p.timestamp)[-1]
    
    if last_pos.track is None:
        return {"predictions": []}
        
    import predictor
    
    # Predictions geometriques (rapides)
    predictions = predictor.get_predictions(last_pos.lat, last_pos.lon, last_pos.track)
    
    # Trouver le dirigeant
    flottes = load_flottes()
    pays_nom = "Inconnu"
    dirigeant = "Inconnu"
    for item in flottes:
        if any(j.get("icao24", "").lower() == icao24.lower() for j in item.get("flotte", [])):
            pays_nom = item["pays"]
            dirigeant = item["dirigeant"]
            break
    
    # Add leader context to each prediction
    for pred in predictions:
        pred["leader"] = dirigeant
        pred["country"] = pays_nom
        
    return {"predictions": predictions}

@app.get("/stats")
def get_stats(db: Session = Depends(get_db), _user: User = Depends(require_auth)):
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

# ─────────────────────────────────────────────────────────────────────
# PIPELINE DE CLASSIFICATION WEBGPU (Couches 2→5 sans Ollama)
# ─────────────────────────────────────────────────────────────────────

@app.get("/classify/pending/{pays}")
def get_pending_flights(pays: str, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """
    Couche 2 — Étape 1/2 (Backend)
    Retourne la liste des vols non-classifiés avec les prompts LLM pré-construits.
    Le frontend soumettra chaque prompt à Llama 3 via WebGPU (WebLLM).
    """
    flottes = load_flottes()
    pays_data = next((item for item in flottes if normaliser(item["pays"]) == normaliser(pays)), None)

    if not pays_data:
        raise HTTPException(status_code=404, detail=f"Pays '{pays}' inconnu.")

    icao24_list = [
        jet["icao24"].lower()
        for jet in pays_data.get("flotte", []) if jet.get("icao24")
    ]
    if not icao24_list:
        return {"vols": [], "context": pays_data}

    vols_non_classes = db.query(Flight).filter(
        Flight.icao24.in_(icao24_list),
        Flight.classification == None
    ).all()

    context = {
        "pays": pays_data["pays"],
        "dirigeant": pays_data.get("dirigeant", "Inconnu")
    }

    result = []
    for vol in vols_non_classes:
        prompt = classifier.build_classification_prompt(vol, context)
        result.append({
            "id": vol.id,
            "icao24": vol.icao24,
            "departure_airport": vol.departure_airport,
            "arrival_airport": vol.arrival_airport,
            "departure_time": vol.departure_time,
            "duration_minutes": vol.duration_minutes,
            "prompt": prompt
        })

    return {"vols": result, "context": context, "total": len(result)}


class ClassificationResultRequest(BaseModel):
    flight_id: int
    classification: str  # "diplomatique" | "officiel" | "personnel"
    confiance: str = "faible"
    evenement_confirme: str = "aucun"
    sources_consultees: list = []
    signal_alerte: str = "non"
    motif_alerte: str = ""
    raw_response: str = ""


@app.post("/classify/result")
def submit_classification_result(
    payload: ClassificationResultRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth)
):
    """
    Couche 2 — Étape 2/2 (Backend)
    Reçoit la classification générée par WebLLM et la persiste en base.
    Retourne needs_investigation=True si le vol est classifié "personnel".
    """
    vol = db.query(Flight).filter(Flight.id == payload.flight_id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Vol introuvable.")

    classification = payload.classification.lower().strip()
    if classification not in ("diplomatique", "officiel", "personnel"):
        classification = "officiel"

    details = {
        "classification": classification,
        "confiance": payload.confiance,
        "evenement_confirme": payload.evenement_confirme,
        "sources_consultees": payload.sources_consultees,
        "signal_alerte": payload.signal_alerte,
        "motif_alerte": payload.motif_alerte,
        "raw_response": payload.raw_response[:500]
    }

    vol.classification = classification
    vol.classification_details = json.dumps(details, ensure_ascii=False)
    db.commit()

    return {
        "status": "ok",
        "flight_id": vol.id,
        "classification": classification,
        "needs_investigation": classification == "personnel"
    }


@app.post("/investigate/prepare/{flight_id}")
def prepare_investigation(
    flight_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth)
):
    """
    Couches 3+4 — Python pur (Backend)
    Lance la collecte OSINT (couche 3) et Dijkstra (couche 4) sans LLM.
    Retourne les données brutes + les prompts LLM pré-construits pour
    que le frontend génère le graphe (couche 4a) et le rapport (couche 5)
    via WebLLM (WebGPU).
    """
    vol = db.query(Flight).filter(Flight.id == flight_id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Vol introuvable.")

    if vol.classification != "personnel":
        raise HTTPException(
            status_code=400,
            detail="Ce vol n'est pas classifié 'personnel'. L'investigation est réservée aux vols personnels."
        )

    flottes = load_flottes()
    context = {"pays": "Inconnu", "dirigeant": "Inconnu"}
    for item in flottes:
        for jet in item.get("flotte", []):
            if jet.get("icao24", "").lower() == vol.icao24.lower():
                context = {"pays": item["pays"], "dirigeant": item.get("dirigeant", "Inconnu")}
                break

    try:
        data = classifier.prepare_investigation_data(vol, context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur pipeline couches 3+4: {str(e)}")

    return {
        "flight_id": flight_id,
        "graph_prompt": data["graph_prompt"],
        "detective_prompt": data["detective_prompt"],
        "osint_summary": {
            "nb_presse": len(data["osint_data"].get("press", [])),
            "nb_famille": len(data["osint_data"].get("family_tree", [])),
            "nb_actifs": len(data["osint_data"].get("assets_at_destination", [])),
            "nb_offshore": len(data["osint_data"].get("offshore_leaks", []))
        },
        "graph_results": data["graph_results"],
        "meta": data["meta"]
    }


class InvestigationReportRequest(BaseModel):
    investigation_report: str
    knowledge_graph: str = "{}"
    risk_score: int = 0


@app.post("/investigate/report/{flight_id}")
def submit_investigation_report(
    flight_id: int,
    payload: InvestigationReportRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth)
):
    """
    Couche 5 — Étape finale (Backend)
    Reçoit le rapport détective généré par WebLLM et le persiste en base.
    """
    vol = db.query(Flight).filter(Flight.id == flight_id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Vol introuvable.")

    vol.investigation_report = payload.investigation_report
    vol.knowledge_graph = payload.knowledge_graph
    vol.risk_score = max(0, min(10, payload.risk_score))
    db.commit()

    return {
        "status": "ok",
        "flight_id": flight_id,
        "risk_score": vol.risk_score,
        "message": "Rapport d'investigation sauvegardé avec succès."
    }


# ─────────────────────────────────────────────────────────────────────
# PIPELINE CREWAI — Investigation autonome multi-agents (Couches 3+4+5)
# ─────────────────────────────────────────────────────────────────────

import investigation_crew
from threading import Thread

# Stockage en mémoire des investigations en cours / terminées
# Structure : { flight_id: { "status": "pending|running|done|error", "result": {...} } }
_investigation_cache: dict = {}


def _resolve_context(vol: Flight) -> dict:
    """Résout le dirigeant et le pays à partir du vol via la flotte."""
    flottes = load_flottes()
    for item in flottes:
        for jet in item.get("flotte", []):
            if jet.get("icao24", "").lower() == vol.icao24.lower():
                return {
                    "pays": item["pays"],
                    "dirigeant": item.get("dirigeant", "Inconnu"),
                    "photo_url": item.get("photo_url", ""),
                }
    return {"pays": "Inconnu", "dirigeant": "Inconnu", "photo_url": ""}


def _run_crew_background(flight_id: int, vol_data: dict, db_url: str, model_id: str):
    """
    Exécute l'investigation CrewAI dans un thread séparé (non-bloquant).
    Met à jour _investigation_cache et persiste le résultat en base.
    """
    _investigation_cache[flight_id]["status"] = "running"
    _investigation_cache[flight_id]["active_agent"] = "osint"
    _investigation_cache[flight_id]["last_message"] = "Initialisation..."

    def status_updater(agent_id: str, message: str):
        if flight_id in _investigation_cache:
            _investigation_cache[flight_id]["active_agent"] = agent_id
            _investigation_cache[flight_id]["last_message"] = message[:200]

    try:
        result = investigation_crew.investigate(
            dirigeant=vol_data["dirigeant"],
            pays=vol_data["pays"],
            destination=vol_data["destination"],
            date_vol=vol_data["date_vol"],
            duree_sejour=vol_data.get("duree_sejour", "Inconnue"),
            context_extra=f"ICAO24: {vol_data.get('icao24', '')} | Callsign: {vol_data.get('callsign', '')}",
            status_updater=status_updater,
            model_id=model_id,
        )

        if result.error:
            _investigation_cache[flight_id] = {
                "status": "error",
                "error": result.error,
                "final_report": result.final_report,
            }
        else:
            # Persiste en base via une nouvelle session SQLAlchemy
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            eng = create_engine(db_url, connect_args={"check_same_thread": False})
            Sess = sessionmaker(bind=eng)
            db2 = Sess()
            try:
                v = db2.query(Flight).filter(Flight.id == flight_id).first()
                if v:
                    v.investigation_report = result.final_report
                    v.knowledge_graph = json.dumps(result.graph_json, ensure_ascii=False)
                    v.risk_score = result.risk_score
                    db2.commit()
            finally:
                db2.close()

            _investigation_cache[flight_id] = {
                "status": "done",
                "final_report": result.final_report,
                "graph_json": result.graph_json,
                "sources": result.sources,
                "risk_score": result.risk_score,
                "osint_report": result.osint_report,
            }

    except Exception as e:
        _investigation_cache[flight_id] = {
            "status": "error",
            "error": str(e),
            "final_report": f"**Erreur inattendue :** {str(e)}",
        }


class CrewRunRequest(BaseModel):
    model_id: str = "groq/llama-3.3-70b-versatile"

@app.post("/investigate/run/{flight_id}")
def run_crewai_investigation(
    flight_id: int,
    payload: CrewRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """
    🚀 Lance le pipeline CrewAI d'investigation multi-agents en arrière-plan.

    Remplace /investigate/prepare en offrant une investigation beaucoup plus profonde :
    - Agent 1 (Traqueur OSINT) : recherche adaptative et itérative
    - Agent 2 (Cartographe)    : construction du graphe de connexions
    - Agent 3 (Procureur)      : rapport final + score de risque

    Le résultat est accessible via GET /investigate/status/{flight_id}.
    Durée estimée : 1-5 minutes selon le modèle LLM configuré.
    """
    vol = db.query(Flight).filter(Flight.id == flight_id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Vol introuvable.")

    # Vérifie si une investigation est déjà en cours pour ce vol
    cached = _investigation_cache.get(flight_id)
    if cached and cached.get("status") in ("pending", "running"):
        return {
            "status": cached["status"],
            "flight_id": flight_id,
            "message": "Investigation déjà en cours — consultez GET /investigate/status/{flight_id}",
        }

    # Résout le contexte (dirigeant, pays)
    context = _resolve_context(vol)

    # Calcule la durée du séjour
    duree_sejour = "Inconnue"
    if vol.departure_time and vol.arrival_time:
        duree_h = (vol.arrival_time - vol.departure_time) / 3600
        duree_sejour = f"{round(duree_h, 1)} heures"

    date_vol = "Inconnue"
    if vol.departure_time:
        date_vol = datetime.fromtimestamp(vol.departure_time).strftime("%Y-%m-%d")

    vol_data = {
        "dirigeant": context["dirigeant"],
        "pays": context["pays"],
        "destination": vol.arrival_airport or "Inconnue",
        "date_vol": date_vol,
        "duree_sejour": duree_sejour,
        "icao24": vol.icao24,
        "callsign": vol.callsign or "",
    }

    # Initialise le cache
    _investigation_cache[flight_id] = {"status": "pending"}

    # Lance l'investigation dans un thread non-bloquant
    thread = Thread(
        target=_run_crew_background,
        args=(flight_id, vol_data, SQLALCHEMY_DATABASE_URL, payload.model_id),
        daemon=True,
    )
    thread.start()

    return {
        "status": "pending",
        "flight_id": flight_id,
        "dirigeant": context["dirigeant"],
        "pays": context["pays"],
        "destination": vol_data["destination"],
        "message": (
            "Investigation CrewAI lancée en arrière-plan. "
            "Consultez GET /investigate/status/{flight_id} pour suivre la progression."
        ),
        "poll_url": f"/investigate/status/{flight_id}",
    }


@app.get("/investigate/status/{flight_id}")
def get_investigation_status(
    flight_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """
    📊 Retourne le statut et le résultat de l'investigation CrewAI.

    Statuts possibles :
    - "not_started" : Aucune investigation lancée pour ce vol
    - "pending"     : En attente de démarrage
    - "running"     : Agents IA en cours d'investigation
    - "done"        : Rapport complet disponible
    - "error"       : Erreur survenue (détail dans "error")

    Le frontend peut appeler cet endpoint toutes les 10 secondes (polling).
    """
    vol = db.query(Flight).filter(Flight.id == flight_id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Vol introuvable.")

    cached = _investigation_cache.get(flight_id)

    # Si pas en cache, vérifie si un rapport existe en base (investigation précédente)
    if not cached:
        if vol.investigation_report:
            return {
                "status": "done",
                "flight_id": flight_id,
                "final_report": vol.investigation_report,
                "graph_json": json.loads(vol.knowledge_graph or "{}"),
                "risk_score": vol.risk_score or 0,
                "sources": [],
                "from_cache": False,
            }
        return {"status": "not_started", "flight_id": flight_id}

    response = {"flight_id": flight_id, **cached}

    # Si terminé avec succès, ajoute les métadonnées du vol
    if cached.get("status") == "done":
        response["meta"] = {
            "icao24": vol.icao24,
            "callsign": vol.callsign,
            "departure": vol.departure_airport,
            "arrival": vol.arrival_airport,
        }

    return response


@app.post("/classify/{pays}")
def classify_flights(pays: str, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """
    Point d'entrée de compatibilité — redirige vers GET /classify/pending/{pays}.
    La classification est désormais gérée par WebLLM (WebGPU) dans le navigateur.
    """
    flottes = load_flottes()
    pays_data = next((item for item in flottes if normaliser(item["pays"]) == normaliser(pays)), None)
    if not pays_data:
        raise HTTPException(status_code=404, detail=f"Pays '{pays}' inconnu.")

    return {
        "status": "webgpu_pipeline",
        "pays": pays_data["pays"],
        "message": "La classification utilise désormais WebLLM (WebGPU). Appelez GET /classify/pending/{pays} pour récupérer les vols et prompts, puis POST /classify/result pour soumettre les résultats.",
        "next_step": f"/classify/pending/{pays_data['pays']}"
    }

@app.get("/investigation/{flight_id}")
def get_investigation_report(flight_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """
    Retourne le rapport d'investigation complet pour un vol donné.
    Inclut le rapport détective, le score de risque et les détails de classification.
    """
    vol = db.query(Flight).filter(Flight.id == flight_id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Vol introuvable.")
    
    if not vol.investigation_report:
        raise HTTPException(status_code=404, detail="Aucun rapport d'investigation disponible pour ce vol. Seuls les vols classifiés 'personnel' génèrent un rapport.")
    
    classification_details = {}
    if vol.classification_details:
        try:
            classification_details = json.loads(vol.classification_details)
        except Exception:
            classification_details = {"raw": vol.classification_details}
    
    return {
        "flight_id": vol.id,
        "icao24": vol.icao24,
        "departure_airport": vol.departure_airport,
        "arrival_airport": vol.arrival_airport,
        "departure_time": vol.departure_time,
        "classification": vol.classification,
        "classification_details": classification_details,
        "risk_score": vol.risk_score,
        "investigation_report": vol.investigation_report
    }

@app.get("/investigation/{flight_id}/graph")
def get_investigation_graph(flight_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """
    Retourne le graphe relationnel (nœuds + arêtes) d'un vol investigué.
    Format JSON prêt à être visualisé par le frontend.
    """
    vol = db.query(Flight).filter(Flight.id == flight_id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Vol introuvable.")
    
    if not vol.knowledge_graph:
        raise HTTPException(status_code=404, detail="Aucun graphe relationnel disponible pour ce vol.")
    
    try:
        graph_data = json.loads(vol.knowledge_graph)
    except Exception:
        raise HTTPException(status_code=500, detail="Erreur de parsing du graphe relationnel.")
    
    return {
        "flight_id": vol.id,
        "risk_score": vol.risk_score,
        "graph": graph_data
    }

@app.post("/investigate/{flight_id}")
def trigger_investigation_legacy(flight_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """
    Point d'entrée de compatibilité — redirige vers le pipeline WebGPU.
    L'investigation utilise désormais WebLLM (WebGPU) dans le navigateur.
    Appelez POST /investigate/prepare/{flight_id} pour lancer les couches 3+4,
    puis POST /investigate/report/{flight_id} pour soumettre le rapport WebLLM.
    """
    vol = db.query(Flight).filter(Flight.id == flight_id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Vol introuvable.")

    return {
        "status": "webgpu_pipeline",
        "flight_id": flight_id,
        "message": "L'investigation utilise désormais WebLLM (WebGPU).",
        "next_steps": [
            f"POST /investigate/prepare/{flight_id}  → OSINT + Dijkstra (Python pur)",
            f"POST /investigate/report/{flight_id}   → Soumettre le rapport généré par WebLLM"
        ]
    }

@app.get("/score/{pays}")
def get_score(pays: str, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
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

# Route supprimée car redondante avec celle définie plus bas


@app.get("/classement")
def get_classement(db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    from utils import get_classement_logic
    return get_classement_logic(db)


@app.get("/health")
def health_check():
    """
    Route de contrôle de santé du service.
    """
    return {"status": "ok", "version": "1.0.0"}

from fastapi.responses import Response

@app.get("/proxy-image")
def proxy_image(url: str):
    """Proxy image pour contourner les blocages anti-hotlink (CORS/Referrer) du navigateur."""
    try:
        resp = http_requests.get(url, headers={"User-Agent": "JetWatch/1.0 (contact@jetwatch.local)"}, timeout=10)
        if resp.status_code != 200:
            raise HTTPException(status_code=404, detail="Image introuvable ou accès refusé")
        return Response(content=resp.content, media_type=resp.headers.get("Content-Type", "image/jpeg"))
    except Exception:
        raise HTTPException(status_code=404, detail="Image introuvable")

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
            "photo_url": item.get("photo_url", ""),
            "type_regime": item.get("type_regime", "Inconnu"),
            "jets_verifies": jets_verifies
        })
    result.sort(key=lambda x: normaliser(x["pays"]))
    return result

@app.get("/vols/{pays}")
def get_vols_pays(pays: str, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
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
        positions = sorted(v.positions, key=lambda p: p.timestamp)
        path = [[p.lat, p.lon] for p in positions]
        exact_departure = path[0] if path else None
        exact_arrival = path[-1] if path else None
        
        result.append({
            "id": v.id,
            "icao24": v.icao24,
            "tail_number": icao24_map.get(v.icao24.lower(), "Inconnu"),
            "callsign": v.callsign,
            "departure_airport": v.departure_airport,
            "arrival_airport": v.arrival_airport,
            "exact_departure": exact_departure,
            "exact_arrival": exact_arrival,
            "departure_time": v.departure_time,
            "arrival_time": v.arrival_time,
            "duration_minutes": v.duration_minutes,
            "classification": v.classification,
            "co2_kg": v.co2_kg,
            "risk_score": v.risk_score,
            "has_investigation": v.investigation_report is not None and len(v.investigation_report or "") > 0,
            "path": path
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

@app.get("/osint/lookup/{tail_number}")
@limiter.limit("20/minute")
def osint_lookup(tail_number: str, request: Request):
    """
    Scanne la base locale OpenSky pour trouver le code ICAO d'un avion
    à partir de son immatriculation (Tail Number).
    """
    csv_path = os.path.join(os.path.dirname(__file__), "aircraftDatabase.csv")
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=503, detail="Base de données OSINT locale non trouvée. Veuillez télécharger aircraftDatabase.csv depuis OpenSky.")
        
    tail_norm = tail_number.replace('-', '').upper()
    
    try:
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                reg = row.get('registration', '').upper().replace('-', '')
                if reg == tail_norm or row.get('registration', '').upper() == tail_number.upper():
                    return {
                        "status": "found",
                        "icao24": row.get('icao24', '').lower(),
                        "tail_number": row.get('registration', ''),
                        "manufacturer": row.get('manufacturername', ''),
                        "model": row.get('model', ''),
                        "operator": row.get('operator', '') or row.get('owner', '')
                    }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de scan OSINT: {str(e)}")
        
from pydantic import BaseModel

class JetAddRequest(BaseModel):
    pays: str
    icao24: str
    tail_number: str
    description: str

@app.get("/flotte/{pays}")
def get_flotte(pays: str, db: Session = Depends(get_db)):
    """
    Retourne la liste des jets de la flotte présidentielle pour un pays donné.
    Combine les données SQL (TargetFleet) et les données du fichier JSON de référence.
    """
    # Recherche de la cible dans la base SQL
    target = db.query(Target).filter(Target.pays.ilike(pays)).first()
    
    jets_sql = []
    if target:
        fleet_rows = db.query(TargetFleet).filter(TargetFleet.target_id == target.id).all()
        jets_sql = [
            {
                "icao24": row.icao24,
                "tail_number": row.tail_number,
                "description": row.description,
                "verifie": row.verifie,
                "source": "sql"
            }
            for row in fleet_rows
        ]
    
    # Enrichissement depuis le fichier JSON de référence (jets_africains.json / flottes JSON)
    jets_json = []
    try:
        flottes = load_flottes()
        pays_data = next(
            (item for item in flottes if normaliser(item.get("pays", "")) == normaliser(pays)),
            None
        )
        if pays_data:
            for jet in pays_data.get("flotte", []):
                icao = (jet.get("icao24") or "").lower()
                # Eviter les doublons avec la BDD SQL
                already_in_sql = any(j["icao24"] == icao for j in jets_sql if j["icao24"])
                if not already_in_sql:
                    jets_json.append({
                        "icao24": icao or None,
                        "tail_number": jet.get("tail_number") or jet.get("registration") or "?",
                        "description": jet.get("description") or jet.get("model") or "Modèle inconnu",
                        "verifie": jet.get("verifie", False),
                        "source": "json"
                    })
    except Exception as e:
        pass  # Fichier JSON absent ou corrompu, on continue avec les données SQL uniquement

    flotte_combinee = jets_sql + jets_json

    return {"pays": pays, "flotte": flotte_combinee, "total": len(flotte_combinee)}


@app.post("/flotte/ajouter")
def ajouter_jet(jet_data: JetAddRequest, db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    """
    Ajoute un jet présidentiel vérifié via OSINT dans la base de données SQL.
    Nécessite le rôle administrateur.
    """
    try:
        # Trouver la cible (Pays ou VIP)
        target = db.query(Target).filter(Target.pays == jet_data.pays).first()
        # Fallback insensitif à la casse si besoin
        if not target:
            target = db.query(Target).filter(Target.pays.ilike(jet_data.pays)).first()
            
        if not target:
            raise HTTPException(status_code=404, detail=f"Pays '{jet_data.pays}' non trouvé dans la liste.")
            
        # Vérifier si ce jet existe déjà pour cette cible
        existing_jet = db.query(TargetFleet).filter(TargetFleet.target_id == target.id, TargetFleet.icao24 == jet_data.icao24.lower()).first()
        if existing_jet:
            raise HTTPException(status_code=400, detail="Ce jet est déjà dans la flotte de ce pays.")
            
        new_jet = TargetFleet(
            target_id=target.id,
            icao24=jet_data.icao24.lower(),
            tail_number=jet_data.tail_number.upper(),
            description=jet_data.description,
            verifie=True
        )
        db.add(new_jet)
        db.commit()
        
        return {"status": "success", "message": f"Jet ajouté avec succès à la flotte de {jet_data.pays}"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

class VIPAddRequest(BaseModel):
    nom: str

import requests as http_requests

def _search_wikipedia_photo(name: str) -> dict:
    """
    Recherche automatique d'une photo et d'une description via l'API Wikipedia.
    Essaie d'abord en anglais (plus riche pour les VIP internationaux), puis en français.
    """
    for lang in ["en", "fr"]:
        try:
            url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{name.replace(' ', '_')}"
            resp = http_requests.get(url, timeout=8, headers={"User-Agent": "JetWatch/1.0 (contact@jetwatch.local)"})
            if resp.status_code == 200:
                data = resp.json()
                photo = data.get("thumbnail", {}).get("source", "")
                # Prendre l'image en plus haute résolution si disponible
                original = data.get("originalimage", {}).get("source", "")
                description = data.get("description", "")
                extract = data.get("extract", "")
                if photo or original:
                    return {
                        "photo_url": original or photo,
                        "thumbnail": photo,
                        "description": description,
                        "extract": extract[:200] if extract else ""
                    }
        except Exception:
            continue
    
    # Fallback: essayer la recherche Wikipedia
    try:
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={name}&format=json&srlimit=1"
        resp = http_requests.get(search_url, timeout=8, headers={"User-Agent": "JetWatch/1.0 (contact@jetwatch.local)"})
        if resp.status_code == 200:
            results = resp.json().get("query", {}).get("search", [])
            if results:
                title = results[0]["title"]
                summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}"
                resp2 = http_requests.get(summary_url, timeout=8, headers={"User-Agent": "JetWatch/1.0 (contact@jetwatch.local)"})
                if resp2.status_code == 200:
                    data = resp2.json()
                    photo = data.get("thumbnail", {}).get("source", "")
                    original = data.get("originalimage", {}).get("source", "")
                    if photo or original:
                        return {
                            "photo_url": original or photo,
                            "thumbnail": photo,
                            "description": data.get("description", ""),
                            "extract": data.get("extract", "")[:200]
                        }
    except Exception:
        pass
    
    return {"photo_url": "", "thumbnail": "", "description": "", "extract": ""}

@app.post("/vip/ajouter")
def ajouter_vip(vip_data: VIPAddRequest, db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    """
    Ajoute une nouvelle personnalité (VIP) à la base de données SQL.
    Recherche automatiquement sa photo via Wikipedia.
    Nécessite le rôle administrateur.
    """
    try:
        # Vérifier si le VIP existe déjà
        existing_target = db.query(Target).filter(Target.pays.ilike(vip_data.nom)).first()
        if existing_target:
            raise HTTPException(status_code=400, detail="Cette personnalité existe déjà.")
        
        # Recherche automatique de la photo
        wiki_data = _search_wikipedia_photo(vip_data.nom)
        
        new_target = Target(
            pays=vip_data.nom,
            dirigeant=vip_data.nom,
            type_regime=wiki_data.get("description", "VIP") or "VIP",
            photo_url=wiki_data.get("photo_url", "")
        )
        db.add(new_target)
        db.flush() # Flush to get the Target ID if needed, though we link by Target ID implicitly in our schema (Wait, TargetFleet uses target_id)
        
        # OSINT pour trouver le jet privé
        jet_info = find_vip_jet(vip_data.nom)
        if jet_info:
            new_fleet = TargetFleet(
                target_id=new_target.id,
                icao24=jet_info["icao24"],
                tail_number=jet_info["tail_number"],
                description=jet_info["description"]
            )
            db.add(new_fleet)
            
        db.commit()
            
        return {
            "status": "success",
            "message": f"Personnalité {vip_data.nom} ajoutée avec succès." + (f" Jet détecté: {jet_info['tail_number']}" if jet_info else ""),
            "photo_url": wiki_data.get("photo_url", ""),
            "thumbnail": wiki_data.get("thumbnail", ""),
            "description": wiki_data.get("description", ""),
            "extract": wiki_data.get("extract", ""),
            "jet_found": bool(jet_info),
            "jet_details": jet_info
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

AFRICAN_PREFIXES = {
    "afrique du sud": ["ZS", "ZT", "ZU"],
    "algérie": ["7T"],
    "angola": ["D2"],
    "bénin": ["TY"],
    "botswana": ["A2"],
    "burkina faso": ["XT"],
    "burundi": ["9U"],
    "cameroun": ["TJ"],
    "cap-vert": ["D4"],
    "république centrafricaine": ["TL"],
    "comores": ["D6"],
    "congo-brazzaville": ["TN"],
    "république démocratique du congo": ["9Q"],
    "côte d'ivoire": ["TU"],
    "djibouti": ["J2"],
    "égypte": ["SU"],
    "érythrée": ["E3"],
    "eswatini": ["3D"],
    "éthiopie": ["ET"],
    "gabon": ["TR"],
    "gambie": ["C5"],
    "ghana": ["9G"],
    "guinée": ["3X"],
    "guinée-bissau": ["J5"],
    "guinée équatoriale": ["3C"],
    "kenya": ["5Y"],
    "lesotho": ["7P"],
    "libéria": ["A8"],
    "libye": ["5A"],
    "madagascar": ["5R"],
    "malawi": ["7Q"],
    "mali": ["TZ"],
    "mauritanie": ["5T"],
    "maurice": ["3B"],
    "maroc": ["CN"],
    "mozambique": ["C9"],
    "namibie": ["V5"],
    "niger": ["5U"],
    "nigeria": ["5N"],
    "ouganda": ["5X"],
    "rwanda": ["9XR"],
    "são tomé-et-príncipe": ["S9"],
    "sénégal": ["6V"],
    "seychelles": ["S7"],
    "sierra leone": ["9L"],
    "somalie": ["6O"],
    "soudan": ["ST"],
    "soudan du sud": ["Z8"],
    "tanzanie": ["5H"],
    "tchad": ["TT"],
    "togo": ["5V"],
    "tunisie": ["TS"],
    "zambie": ["9J"],
    "zimbabwe": ["Z"]
}

VIP_MANUFACTURERS = ["dassault", "gulfstream", "boeing", "airbus", "bombardier", "embraer", "fokker", "ilyushin", "tupolev"]

EXCLUDED_KEYWORDS = ["airlines", "airways", "air lines", "cargo", "express", "freight", "logistics", "charter", "leasing", "rental"]
GOV_KEYWORDS = ["government", "gouvernement", "republic", "république", "air force", "force", "armée", "armee", "etat", "state", "presid", "repubblica"]

def fallback_osint_web_search(pays: str, prefixes: list) -> list:
    """
    Recherche autonome multi-sources sur le web pour trouver les immatriculations
    des jets VIP/gouvernementaux manquants dans la base CSV locale.
    Sources: Wikipedia API, DuckDuckGo (EN+FR), scraping direct de pages spécialisées.
    """
    if not prefixes:
        return []
        
    found_candidates = []
    seen_regs = set()
    
    # Construire un pattern regex pour tous les préfixes du pays
    # Supporte TY-XXX, TY XXX, TYXXX, et aussi les variantes dans les tableaux wiki
    prefix_pattern = '|'.join(re.escape(p) for p in prefixes)
    reg_pattern = re.compile(
        rf'\b({prefix_pattern})[- ]([A-Z0-9]{{2,4}})\b',
        re.IGNORECASE
    )
    
    # Mots courants qui ressemblent à des immatriculations (faux positifs)
    FALSE_POSITIVES = {
        "PE", "PES", "PICAL", "PING", "PICA", "RANT", "RANS", "HE", "HIS",
        "HAT", "HEN", "HERE", "HEM", "HEY", "HEX", "THE", "HAN", "HAS",
        "WO", "WAS", "ORK", "OUR", "OWN", "OOL", "OOK", "OU", "OO"
    }
    
    def _extract_and_add(text: str, source: str = "OSINT Web"):
        """Extrait les immatriculations d'un texte et les ajoute aux candidats."""
        matches = reg_pattern.findall(text.upper())
        for prefix_part, suffix_part in matches:
            if suffix_part.upper() in FALSE_POSITIVES:
                continue
            # Reconstituer l'immatriculation au format standard PREFIX-SUFFIX
            reg = f"{prefix_part}-{suffix_part}".upper()
            if reg in seen_regs or len(suffix_part) < 2:
                continue
            seen_regs.add(reg)
            
            # Chercher un code hex ICAO24 à proximité dans le texte
            hex_matches = re.findall(r'\b([0-9A-Fa-f]{6})\b', text)
            icao24 = hex_matches[0].lower() if hex_matches else f"web_{reg.replace('-', '').lower()}"
            
            # Essayer de deviner le modèle depuis le contexte
            model = "VIP Jet"
            for kw in ["Boeing 737", "Boeing 727", "Boeing 787", "BBJ", "Falcon 900", "Falcon 7X",
                        "Falcon 50", "Gulfstream", "Global Express", "Challenger", "Airbus A319",
                        "Airbus A320", "Airbus ACJ", "Embraer Legacy", "Embraer Lineage",
                        "Hercules", "C-130", "L-100", "Beechcraft", "King Air", "Hawker"]:
                if kw.lower() in text.lower():
                    model = kw
                    break
            
            manufacturer = "Inconnu"
            for m in ["Boeing", "Dassault", "Gulfstream", "Bombardier", "Airbus", "Embraer", "Lockheed", "Beechcraft"]:
                if m.lower() in text.lower():
                    manufacturer = m
                    break
            
            found_candidates.append({
                "icao24": icao24,
                "tail_number": reg,
                "manufacturer": f"{manufacturer} ({source})",
                "model": model,
                "operator": f"Gouvernement de {pays} (Déduit)"
            })
    
    # ── SOURCE 1 : Wikipedia API (la plus fiable) ──
    pays_underscore = pays.replace(' ', '_').replace("'", '%27')
    wiki_pages = [
        "Air_transports_of_heads_of_state_and_government",
        "Benin_Air_Force" if "bénin" in pays.lower() or "benin" in pays.lower() else f"{pays.replace(' ', '_')}_Air_Force",
        f"Forces_armées_{pays_underscore}",
    ]
    for page in wiki_pages:
        for lang in ["en", "fr"]:
            try:
                url = f"https://{lang}.wikipedia.org/w/api.php?action=parse&page={page}&prop=wikitext&format=json&redirects=1"
                resp = http_requests.get(url, timeout=10, headers={"User-Agent": "JetWatch/1.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
                    if wikitext and any(p.lower() in wikitext.lower() for p in prefixes):
                        _extract_and_add(wikitext, f"Wikipedia ({lang})")
            except Exception:
                continue
    
    # ── SOURCE 2 : DuckDuckGo (requêtes diversifiées EN + FR) ──
    queries = [
        f'"{pays}" presidential aircraft registration',
        f'"{pays}" government VIP jet fleet',
        f'avion présidentiel "{pays}" immatriculation',
        f'"{pays}" air force aircraft fleet registration',
        f'"{" OR ".join(prefixes)}" aircraft government',
        f'site:planespotters.net "{pays}" government',
        f'site:jetphotos.com "{pays}" government',
    ]
    
    try:
        with DDGS() as ddgs:
            for q in queries:
                try:
                    results = list(ddgs.text(q, max_results=8, region='wt-wt'))
                    for r in results:
                        text = r.get("body", "") + " " + r.get("title", "") + " " + r.get("href", "")
                        _extract_and_add(text, "DuckDuckGo")
                        
                        # Si un résultat vient de planespotters/jetphotos, essayer de scraper la page
                        href = r.get("href", "")
                        if any(domain in href for domain in ["planespotters.net", "jetphotos.com", "airport-data.com"]):
                            try:
                                page_resp = http_requests.get(href, timeout=8, headers={"User-Agent": "JetWatch/1.0"})
                                if page_resp.status_code == 200:
                                    _extract_and_add(page_resp.text, "Planespotters/JetPhotos")
                            except Exception:
                                continue
                except Exception:
                    continue
    except Exception as e:
        print(f"Erreur DuckDuckGo OSINT: {e}")
    
    # ── SOURCE 3 : Recherche ciblée par préfixe dans des registres en ligne ──
    for prefix in prefixes:
        try:
            url = f"https://www.airport-data.com/api/ac_reg_list.json?prefix={prefix}"
            resp = http_requests.get(url, timeout=8, headers={"User-Agent": "JetWatch/1.0"})
            if resp.status_code == 200:
                _extract_and_add(resp.text, "Airport-Data Registry")
        except Exception:
            continue
    
    print(f"[OSINT Fallback] {pays}: {len(found_candidates)} candidat(s) trouvé(s) via recherche web multi-sources.")
    return found_candidates

@app.get("/osint/discover/{pays}")
@limiter.limit("5/minute")
def osint_discover(pays: str, request: Request, api_key: str = Depends(verify_api_key)):
    """
    Découverte automatisée des jets potentiellement VIP pour un pays donné
    en utilisant les préfixes d'immatriculation OACI.
    Filtre les compagnies commerciales classiques.
    Pour les VIP, scanne par propriétaire/opérateur.
    """
    pays_norm = normaliser(pays).strip()
    prefixes = None
    for key, vals in AFRICAN_PREFIXES.items():
        if normaliser(key).strip() == pays_norm:
            prefixes = vals
            break
            
    is_vip_search = False
    
    if not prefixes:
        # Les VIPs n'ont pas de préfixe national, on effectue une recherche sur le nom dans operator/owner
        is_vip_search = True
        
    csv_path = os.path.join(os.path.dirname(__file__), "aircraftDatabase.csv")
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=503, detail="Base de données OSINT locale manquante.")
        
    candidats = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                reg = row.get('registration', '').strip().upper()
                if not reg:
                    continue
                    
                manufacturer = row.get('manufacturername', '').lower()
                model = row.get('model', '').lower()
                operator = (row.get('operator', '') or row.get('owner', '')).lower()
                
                if is_vip_search:
                    # Recherche de VIP par opérateur/propriétaire
                    if pays_norm in operator:
                        candidats.append({
                            "icao24": row.get('icao24', '').lower(),
                            "tail_number": reg,
                            "manufacturer": row.get('manufacturername', ''),
                            "model": row.get('model', ''),
                            "operator": row.get('operator', '') or row.get('owner', '')
                        })
                        if len(candidats) >= 50:
                            break
                else:
                    # Recherche par pays
                    match_prefix = any(reg.startswith(p) for p in prefixes)
                    if match_prefix:
                        # Filtre d'Intelligence : Éliminer les compagnies aériennes commerciales
                        is_commercial = any(kw in operator for kw in EXCLUDED_KEYWORDS)
                        is_gov = any(kw in operator for kw in GOV_KEYWORDS)
                        
                        if is_commercial and not is_gov:
                            continue # Ignorer les vols commerciaux réguliers
                        
                        is_vip = False
                        for vip in VIP_MANUFACTURERS:
                            if vip in manufacturer or vip in model:
                                is_vip = True
                                break
                                
                        if is_vip:
                            candidats.append({
                                "icao24": row.get('icao24', '').lower(),
                                "tail_number": reg,
                                "manufacturer": row.get('manufacturername', ''),
                                "model": row.get('model', ''),
                                "operator": row.get('operator', '') or row.get('owner', '')
                            })
                            
                            if len(candidats) >= 50:
                                break
                                
        if len(candidats) == 0 and not is_vip_search and prefixes:
            print(f"Aucun candidat dans le CSV pour {pays}. Lancement du Fallback Web OSINT...")
            candidats = fallback_osint_web_search(pays, prefixes)
            
            # Auto-apprentissage : injecter dans le CSV
            if candidats:
                try:
                    with open(csv_path, 'a', encoding='utf-8') as csvfile:
                        for c in candidats:
                            if c["icao24"].startswith("web_"):
                                continue # Ne pas sauvegarder les faux hex
                            row = f'"{c["icao24"]}","{c["tail_number"]}","","","{c["model"]}","","","","","{c["operator"]}","","","","","","","","","","","","","false","true","false","",""\n'
                            csvfile.write(row)
                except Exception as e:
                    print(f"Erreur d'écriture dans le CSV: {e}")

        return {"pays": pays, "prefixes": prefixes if prefixes else ["VIP"], "candidats": candidats}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ====================================================================
# OSINT v4 API - Tool Endpoints for ReAct LLM Agent (WebGPU)
# ====================================================================
import osint_agent

@app.get("/api/search/person")
def api_search_person(name: str, country: str = "", context: str = "",
                      session_id: str = "default"):
    """Search person: Wikidata + DuckDuckGo."""
    try:
        return osint_agent.search_person(name, country, context, session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search/company")
def api_search_company(name: str, jurisdiction: str = "",
                       session_id: str = "default"):
    """Search companies: Pappers + OpenCorporates."""
    try:
        return osint_agent.search_company(name, jurisdiction, session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search/property")
def api_search_property(name: str, city: str = "", address: str = "",
                        session_id: str = "default"):
    """Search properties: DVF + DuckDuckGo."""
    try:
        return osint_agent.search_property(name, city, address, session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search/aleph")
def api_search_aleph(name: str, session_id: str = "default"):
    """Search OCCRP Aleph: Panama Papers, Pandora Papers."""
    try:
        return osint_agent.search_aleph(name, session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search/images")
def api_search_images(query: str, max_results: int = 4,
                      session_id: str = "default"):
    """Search images via DuckDuckGo."""
    try:
        return osint_agent.search_images_tool(query, max_results, session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class GraphNodeRequest(BaseModel):
    name: str
    node_type: str
    country: str = ""
    description: str = ""
    address: str = ""
    siren: str = ""
    session_id: str = "default"

@app.post("/api/graph/add-node")
def api_graph_add_node(data: GraphNodeRequest):
    """Add a node to the investigation graph."""
    try:
        return osint_agent.graph_add_node(
            data.name, data.node_type, data.country, data.description,
            data.address, data.siren, data.session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class GraphRelationRequest(BaseModel):
    source: str
    target: str
    relation: str
    confidence: float = 0.5
    evidence_type: str = "speculatif"
    source_url: str = ""
    session_id: str = "default"

@app.post("/api/graph/add-relation")
def api_graph_add_relation(data: GraphRelationRequest):
    """Add a relation (edge) to the graph."""
    try:
        return osint_agent.graph_add_relation(
            data.source, data.target, data.relation,
            data.confidence, data.evidence_type, data.source_url,
            data.session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/graph/pathfind")
def api_graph_pathfind(source: str, target: str,
                       session_id: str = "default"):
    """Run A* pathfinder for max-confidence path."""
    try:
        return osint_agent.graph_pathfind(source, target, session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/graph/export")
def api_graph_export(session_id: str = "default"):
    """Export graph as JSON for frontend (react-force-graph)."""
    try:
        return osint_agent.graph_export(session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/investigate")
def api_investigate(leader: str, country: str, city: str = "",
                    session_id: str = "default"):
    """Full automated investigation (fallback without WebGPU)."""
    try:
        return osint_agent.investigate_full(leader, country, city, session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/session/{session_id}")
def api_reset_session(session_id: str):
    """Reset an investigation session."""
    osint_agent.reset_session(session_id)
    return {"status": "ok", "message": f"Session {session_id} reset."}

@app.post("/admin/test-social-post")
def test_social_post(request: Request):
    """Test manual generation and posting to social media."""
    admin_key = request.headers.get("x-admin-key")
    if admin_key != "jetwatch2026":
        raise HTTPException(status_code=403, detail="Non autorisé")
        
    import social_bot
    social_bot.run_daily_post()
    return {"status": "ok", "message": "Social post triggered manually"}


# ====================================================================
# Agent Detective v2 — Endpoints additionnels
# ====================================================================

@app.get("/api/tts")
async def text_to_speech(text: str, voice: str = "fr-FR-DeniseNeural"):
    """Génère un flux audio MP3 à partir de texte via Edge TTS (Microsoft)."""
    import edge_tts
    from fastapi.responses import StreamingResponse

    async def generate():
        communicate = edge_tts.Communicate(text, voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    return StreamingResponse(generate(), media_type="audio/mpeg")


@app.get("/api/satellite")
def get_satellite_image(lat: float, lon: float, zoom: int = 8):
    """Retourne l'URL d'une vue satellite pour des coordonnées données.
    Utilise les tuiles Esri World Imagery (haute résolution, gratuites pour usage non commercial)."""
    # Calcul simplifié des tuiles XYZ à partir de lat/lon
    import math
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(math.radians(lat)) + 1.0 / math.cos(math.radians(lat))) / math.pi) / 2.0 * n)
    
    tile_url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{zoom}/{y}/{x}"
    
    # On retourne aussi un lien Google Maps statique en fallback
    gmaps_url = f"https://maps.googleapis.com/maps/api/staticmap?center={lat},{lon}&zoom={zoom}&size=600x400&maptype=satellite"
    
    return {
        "satellite_url": tile_url,
        "gmaps_fallback": gmaps_url,
        "lat": lat,
        "lon": lon,
        "zoom": zoom
    }


@app.get("/api/search/family")
def search_family(name: str, country: str = "", session_id: str = "default"):
    """Recherche l'arbre généalogique d'un dirigeant via Wikidata SPARQL + DuckDuckGo."""
    results = {"name": name, "family_members": [], "source": "Wikidata + DuckDuckGo"}
    
    # 1. Recherche Wikidata SPARQL
    try:
        sparql_query = f"""
        SELECT ?person ?personLabel ?relation ?relationLabel WHERE {{
          ?subject rdfs:label "{name}"@fr .
          {{
            ?subject wdt:P26 ?person . BIND("Conjoint(e)" AS ?relation)
          }} UNION {{
            ?subject wdt:P40 ?person . BIND("Enfant" AS ?relation)
          }} UNION {{
            ?subject wdt:P3373 ?person . BIND("Frère/Sœur" AS ?relation)
          }} UNION {{
            ?subject wdt:P22 ?person . BIND("Père" AS ?relation)
          }} UNION {{
            ?subject wdt:P25 ?person . BIND("Mère" AS ?relation)
          }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "fr,en" . }}
        }}
        LIMIT 20
        """
        sparql_url = "https://query.wikidata.org/sparql"
        resp = http_requests.get(sparql_url, params={"query": sparql_query, "format": "json"}, 
                                  headers={"User-Agent": "JetWatch/1.0"}, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            for binding in data.get("results", {}).get("bindings", []):
                member = {
                    "name": binding.get("personLabel", {}).get("value", "Inconnu"),
                    "relation": binding.get("relationLabel", {}).get("value", "Inconnu"),
                    "wikidata_id": binding.get("person", {}).get("value", "").split("/")[-1]
                }
                results["family_members"].append(member)
    except Exception as e:
        results["wikidata_error"] = str(e)
    
    # 2. Recherche DuckDuckGo en fallback
    if not results["family_members"]:
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                search_results = list(ddgs.text(f"{name} family members spouse children {country}", max_results=5))
                for r in search_results:
                    results["family_members"].append({
                        "name": r.get("title", ""),
                        "relation": "Mentionné dans",
                        "source": r.get("href", ""),
                        "snippet": r.get("body", "")[:200]
                    })
        except Exception as e:
            results["ddg_error"] = str(e)
    
    # Enregistrer dans le graphe de session
    if session_id != "default":
        try:
            osint_agent.add_to_graph(session_id, name, results["family_members"], "famille")
        except Exception:
            pass
    
    return results


@app.get("/api/search/salary")
def search_salary(name: str, session_id: str = "default"):
    """Recherche le salaire officiel déclaré d'un dirigeant."""
    results = {"name": name, "salary_info": [], "source": "DuckDuckGo"}
    
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            search_results = list(ddgs.text(
                f"{name} salaire officiel déclaré revenus patrimoine déclaration",
                max_results=5
            ))
            for r in search_results:
                results["salary_info"].append({
                    "title": r.get("title", ""),
                    "source": r.get("href", ""),
                    "snippet": r.get("body", "")[:300]
                })
            
            # Recherche en anglais aussi
            search_results_en = list(ddgs.text(
                f"{name} official salary declared income net worth",
                max_results=3
            ))
            for r in search_results_en:
                results["salary_info"].append({
                    "title": r.get("title", ""),
                    "source": r.get("href", ""),
                    "snippet": r.get("body", "")[:300]
                })
    except Exception as e:
        results["error"] = str(e)
    
    return results


# ─────────────────────────────────────────────────────────────────────────────
# AGENT OSINT — Command R+ (Cohere) avec fallback DuckDuckGo
# ─────────────────────────────────────────────────────────────────────────────

class OsintRunRequest(BaseModel):
    target_name: str
    target_country: str
    target_city: str
    session_id: str = ""


@app.post("/api/osint/run")
def run_osint_agent(
    payload: OsintRunRequest,
    _user: User = Depends(require_auth)
):
    """
    Agent OSINT autonome — utilise Command R+ (Cohere) si COHERE_API_KEY est défini,
    sinon fallback sur DuckDuckGo.
    
    Effectue des recherches sur :
      - Profil politique & antécédents
      - Patrimoine déclaré vs revenus
      - Liens familiaux & offshore
      - Presse récente
    
    Retourne un résumé structuré prêt à être analysé par l'agent détective (WebLLM).
    """
    name = payload.target_name
    country = payload.target_country
    city = payload.target_city

    cohere_key = os.getenv("COHERE_API_KEY", "")
    
    summary = {}
    steps = []

    if cohere_key:
        # ── Mode Cohere Command R+ ──────────────────────────────────────────
        try:
            import cohere
            co = cohere.Client(cohere_key)

            system_prompt = f"""Tu es un agent OSINT expert en investigation des biens mal acquis en Afrique.
Tu dois rechercher des informations sur {name} ({country}) qui vient de voyager vers {city}.
Utilise les sources publiques : OCCRP, Aleph, presse africaine, registres offshore.
Structure ta réponse en JSON avec les clés :
- political_profile: string
- declared_assets: list of strings
- suspected_assets: list of strings
- family_connections: list of strings
- recent_news: list of strings
- risk_assessment: string"""

            response = co.chat(
                model="command-r-plus",
                message=f"Lance l'investigation OSINT sur {name}, {country}, destination {city}.",
                preamble=system_prompt,
                connectors=[{"id": "web-search"}] if cohere_key else [],
            )
            
            raw = response.text
            # Try to parse JSON
            try:
                import re as _re
                json_match = _re.search(r'\{.*\}', raw, _re.DOTALL)
                if json_match:
                    summary = json.loads(json_match.group())
                else:
                    summary = {"raw_analysis": raw}
            except Exception:
                summary = {"raw_analysis": raw}
            
            steps.append({
                "thought": f"Recherche Command R+ sur {name}",
                "action": "COHERE_SEARCH(command-r-plus, web-search)",
                "observation": f"{len(str(summary))} caractères de données collectées"
            })

        except ImportError:
            # cohere package not installed — fallback
            cohere_key = ""
        except Exception as e:
            summary["cohere_error"] = str(e)
            cohere_key = ""

    if not cohere_key:
        # ── Mode fallback DuckDuckGo ────────────────────────────────────────
        summary = {"target": name, "country": country, "destination": city, "findings": {}}
        queries = [
            (f"{name} patrimoine biens immobiliers fortune", "patrimoine"),
            (f"{name} famille enfants proches offshore", "famille"),
            (f"{name} {country} corruption enquête justice", "judiciaire"),
            (f"{name} {city} visite voyage raison officielle", "voyage"),
        ]
        
        with DDGS() as ddgs:
            for query, key in queries:
                try:
                    results = list(ddgs.text(query, max_results=4))
                    summary["findings"][key] = [
                        {"title": r.get("title", ""), "source": r.get("href", ""), "snippet": r.get("body", "")[:300]}
                        for r in results
                    ]
                    steps.append({
                        "thought": f"Recherche DuckDuckGo : {key}",
                        "action": f"DDGS_SEARCH({query[:60]}...)",
                        "observation": f"{len(results)} résultats trouvés"
                    })
                except Exception as e:
                    summary["findings"][key] = []
                    steps.append({
                        "thought": f"Recherche {key} — erreur",
                        "action": f"DDGS_SEARCH({query[:60]}...)",
                        "observation": f"Erreur: {str(e)}"
                    })

    return {
        "status": "ok",
        "agent": "command-r-plus" if os.getenv("COHERE_API_KEY") else "duckduckgo-fallback",
        "target": name,
        "country": country,
        "destination": city,
        "summary": summary,
        "steps": steps,
    }
