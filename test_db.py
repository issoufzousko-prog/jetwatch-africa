import json
from models import Target, TargetFleet, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
engine = create_engine('sqlite:///./jetwatch.db')
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()
with open('data/jets_africains.json', 'r', encoding='utf-8') as f:
    flottes = json.load(f)
print('loaded JSON:', len(flottes))
for i, item in enumerate(flottes):
    try:
        t = Target(pays=item.get('pays'), dirigeant=item.get('dirigeant'), type_regime=item.get('type_regime'), photo_url=item.get('photo_url'))
        db.add(t)
        db.commit()
    except Exception as e:
        print(f'Error at {i}: {item.get("pays")}')
        print(e)
        db.rollback()
