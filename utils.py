import unicodedata

from database import SessionLocal
from models import Target

def normaliser(texte: str) -> str:
    """Supprime les accents et met en minuscules pour comparaison."""
    if not texte:
        return ""
    return ''.join(
        c for c in unicodedata.normalize('NFD', texte.lower())
        if unicodedata.category(c) != 'Mn'
    )

def load_flottes() -> list:
    """Charge le dictionnaire des flottes depuis la base de données SQL."""
    db = SessionLocal()
    try:
        targets = db.query(Target).all()
        result = []
        for t in targets:
            flotte = [{"icao24": f.icao24, "tail_number": f.tail_number, "description": f.description, "verifie": f.verifie} for f in t.fleet]
            result.append({
                "pays": t.pays,
                "dirigeant": t.dirigeant,
                "type_regime": t.type_regime,
                "photo_url": t.photo_url,
                "flotte": flotte
            })
        return result
    except Exception as e:
        print(f"Erreur load_flottes: {e}")
        return []
    finally:
        db.close()

def get_classement_logic(db) -> list:
    """Logique métier pour générer le classement des pays."""
    import scorer
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
                    "photo_url": item.get("photo_url", ""),
                    "score_global": result.get("score_global"),
                    "niveau": result.get("niveau"),
                    "total_vols": result.get("total_vols"),
                    "vols_officiels": result.get("vols_officiels", 0),
                    "vols_personnels": result.get("vols_personnels", 0),
                    "co2_kg": result.get("co2_kg"),
                    "jets_verifies": jets_verifies,
                    "statut": "données disponibles"
                })
            else:
                classement.append({
                    "pays": pays_nom,
                    "dirigeant": dirigeant,
                    "photo_url": item.get("photo_url", ""),
                    "score_global": 0,
                    "niveau": "N/A",
                    "total_vols": 0,
                    "vols_officiels": 0,
                    "vols_personnels": 0,
                    "co2_kg": 0,
                    "jets_verifies": jets_verifies,
                    "statut": "en attente de détection"
                })
        except Exception:
            continue
            
    classement_vols = sorted([c for c in classement if c["total_vols"] > 0], key=lambda x: x["score_global"], reverse=True)
    classement_sans_vols = sorted([c for c in classement if c["total_vols"] == 0], key=lambda x: x["jets_verifies"], reverse=True)
    
    result = classement_vols + classement_sans_vols
    return result[:30]

