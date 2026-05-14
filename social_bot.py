import os
import requests
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Flight
import json
from staticmap import StaticMap, Line, CircleMarker

def get_daily_summary_text(db: Session) -> str:
    """Génère le texte du bilan du jour."""
    from utils import load_flottes, normaliser

    
    # Convertir en timestamp Unix pour la BDD
    hier = datetime.datetime.now() - datetime.timedelta(days=1)
    hier_unix = int(hier.timestamp())
    
    vols = db.query(Flight).filter(
        Flight.departure_time >= hier_unix,
        Flight.co2_kg != None
    ).all()
    
    if not vols:
        return ""
        
    total_vols = len(vols)
    total_co2 = sum((v.co2_kg or 0) for v in vols)
    
    # Trouver l'avion qui a émis le plus
    pire_vol = max(vols, key=lambda v: (v.co2_kg or 0))
    
    # Identifier le pays/dirigeant
    flottes = load_flottes()
    pays_nom = "Inconnu"
    dirigeant = "Inconnu"
    tail_number = "Inconnu"
    
    for item in flottes:
        for jet in item.get("flotte", []):
            if jet.get("icao24", "").lower() == pire_vol.icao24.lower():
                pays_nom = item.get("pays", "Inconnu")
                dirigeant = item.get("dirigeant", "Inconnu")
                tail_number = jet.get("tail_number", "Inconnu")
                break
                
    # Récupérer le classement global pour intégrer le Top 3
    from utils import get_classement_logic
    classement_complet = get_classement_logic(db)

    top_3 = sorted(classement_complet, key=lambda x: x.get("score_global", 0), reverse=True)[:3]
    
    classement_texte = "📊 LE CLASSEMENT DE L'OPACITÉ (TOP 3) :\n"
    for idx, c in enumerate(top_3):
        classement_texte += f"{idx+1}. {c['dirigeant']} ({c['pays']}) - Score: {c['score_global']}/100 | {c['niveau']}\n"
                
    web_url = os.getenv("WEB_URL", "https://jetwatch-africa.com") + "?view=share"
    
    # Formater le texte avec un ton OSINT très accrocheur orienté Afrique/VIP
    texte = (
        f"🚨 ALERTE JETWATCH : Le bilan des dernières 24h est tombé.\n\n"
        f"🌍 Les jets présidentiels africains et les VIP sous surveillance ont secrètement brûlé {int(total_co2 / 1000)} tonnes de CO2 en {total_vols} vols.\n"
        f"🥇 Le pire bilan d'aujourd'hui ? Le jet de {dirigeant} ({pays_nom}) avec {int((pire_vol.co2_kg or 0) / 1000)} tonnes émises sur un seul trajet.\n\n"
        f"{classement_texte}\n"
        f"👀 D'autres chefs d'État et oligarques viennent de décoller vers des destinations non déclarées...\n\n"
        f"👉 Infiltrez notre radar fantôme et traquez exactement OÙ l'argent public s'envole en ce moment-même : {web_url}"
    )
    
    return texte, pire_vol

def generate_flight_map(flight: Flight) -> str:
    """Génère une image de la carte statique de la trajectoire du vol."""
    if not flight or not flight.positions:
        return ""
    
    try:
        positions = json.loads(flight.positions)
        if len(positions) < 2:
            return ""
            
        # Extraire seulement lat/lon
        coords = [(p[1], p[0]) for p in positions] # staticmap veut (lon, lat)
        
        # Initialiser StaticMap avec CARTO Dark theme
        m = StaticMap(1000, 600, url_template='https://cartodb-basemaps-a.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png')
        
        # Dessiner la trajectoire en rouge
        line = Line(coords, '#ef4444', 3)
        m.add_line(line)
        
        # Point de départ (orange) et d'arrivée (vert)
        m.add_marker(CircleMarker(coords[0], '#f59e0b', 8))
        m.add_marker(CircleMarker(coords[-1], '#22c55e', 8))
        
        image = m.render()
        filepath = os.path.join(os.path.dirname(__file__), "flight_map.png")
        image.save(filepath)
        print(f"[SocialBot] Carte générée avec succès : {filepath}")
        return filepath
    except Exception as e:
        print(f"[SocialBot] Erreur lors de la génération de la carte: {e}")
        return ""

def post_to_facebook(text: str, image_path: str = None):
    """Publie un message (avec ou sans image) sur la page Facebook."""
    token = os.getenv("FACEBOOK_PAGE_TOKEN")
    if not token or token.startswith("YOUR_"):
        print("[SocialBot] Jeton Facebook non configuré.")
        return False
        
    try:
        if image_path and os.path.exists(image_path):
            url = f"https://graph.facebook.com/v19.0/me/photos"
            payload = {"message": text, "access_token": token}
            with open(image_path, "rb") as img:
                files = {"source": img}
                response = requests.post(url, data=payload, files=files, timeout=30)
        else:
            url = f"https://graph.facebook.com/v19.0/me/feed"
            payload = {"message": text, "access_token": token}
            response = requests.post(url, data=payload, timeout=15)
            
        if response.status_code == 200:
            print("[SocialBot] Publication Facebook réussie !")
            return True
        else:
            print(f"[SocialBot] Erreur Facebook: {response.text}")
            return False
    except Exception as e:
        print(f"[SocialBot] Exception Facebook: {e}")
        return False

def post_to_twitter(text: str, image_path: str = None):
    """Publie un message (avec ou sans image) sur X (Twitter)."""
    api_key = os.getenv("TWITTER_API_KEY")
    api_secret = os.getenv("TWITTER_API_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_secret = os.getenv("TWITTER_ACCESS_SECRET")
    
    if not all([api_key, api_secret, access_token, access_secret]) or api_key.startswith("YOUR_"):
        print("[SocialBot] Clés Twitter non configurées.")
        return False
        
    try:
        import tweepy
        client = tweepy.Client(
            consumer_key=api_key, consumer_secret=api_secret,
            access_token=access_token, access_token_secret=access_secret
        )
        
        media_id = None
        if image_path and os.path.exists(image_path):
            auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
            api = tweepy.API(auth)
            media = api.media_upload(image_path)
            media_id = media.media_id
            
        # Twitter a une limite stricte de 280 caractères
        twitter_text = text
        if len(twitter_text) > 275:
            twitter_text = twitter_text[:275] + "..."
            
        if media_id:
            response = client.create_tweet(text=twitter_text, media_ids=[media_id])
        else:
            response = client.create_tweet(text=twitter_text)
            
        print(f"[SocialBot] Publication Twitter réussie ! ID: {response.data['id']}")
        return True
    except ImportError:
        print("[SocialBot] Librairie 'tweepy' non installée.")
        return False
    except Exception as e:
        print(f"[SocialBot] Erreur Twitter: {e}")
        return False

def run_daily_post():
    """Fonction principale appelée par le scheduler."""
    from database import SessionLocal
    print("[SocialBot] Lancement du bilan quotidien...")
    db = SessionLocal()

    try:
        text, pire_vol = get_daily_summary_text(db)
        if not text:
            print("[SocialBot] Aucun vol significatif aujourd'hui. Pas de publication.")
            return
            
        print(f"[SocialBot] Texte généré :\n{text}\n")
        
        # Générer la carte du pire vol
        image_path = None
        if pire_vol:
            image_path = generate_flight_map(pire_vol)
        
        post_to_facebook(text, image_path)
        post_to_twitter(text, image_path)
        
    finally:
        db.close()
