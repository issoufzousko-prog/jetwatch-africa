import json
import os
import unicodedata
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Target, TargetFleet

def normaliser(texte: str) -> str:
    if not texte: return ""
    return ''.join(
        c for c in unicodedata.normalize('NFD', texte.lower())
        if unicodedata.category(c) != 'Mn'
    )

def diag():
    engine = create_engine('sqlite:///jetwatch.db')
    Session = sessionmaker(bind=engine)
    db = Session()
    
    # 1. Check DB targets
    targets = db.query(Target).all()
    print(f"Total targets in DB: {len(targets)}")
    
    # 2. Check JSON targets
    json_path = os.path.join("data", "jets_africains.json")
    with open(json_path, 'r', encoding='utf-8') as f:
        flottes_json = json.load(f)
    print(f"Total targets in JSON: {len(flottes_json)}")
    
    # 3. Test matching
    missing_in_db = []
    mismatch_norm = []
    
    json_names_norm = {normaliser(item["pays"]): item["pays"] for item in flottes_json if "pays" in item}
    
    for item in flottes_json:
        name = item.get("pays")
        if not name: continue
        
        # Exact match
        db_target = db.query(Target).filter(Target.pays == name).first()
        if not db_target:
            # Normalized match
            db_targets = db.query(Target).all()
            found = False
            for t in db_targets:
                if normaliser(t.pays) == normaliser(name):
                    found = True
                    break
            if not found:
                missing_in_db.append(name)
            else:
                mismatch_norm.append(name)
                
    print(f"Missing in DB (exact): {len(missing_in_db)}")
    if missing_in_db:
        print(f"Sample missing: {missing_in_db[:5]}")
        
    print(f"Mismatch but normalized match: {len(mismatch_norm)}")
    if mismatch_norm:
        print(f"Sample mismatch: {mismatch_norm[:5]}")

    # 4. Check if any 500 error triggers in load_flottes
    try:
        from main import load_flottes
        f = load_flottes()
        print(f"load_flottes() returned {len(f)} items")
    except Exception as e:
        print(f"load_flottes() CRASHED: {e}")

if __name__ == "__main__":
    diag()
