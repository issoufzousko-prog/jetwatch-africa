import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Récupération de l'URL de base de données depuis l'environnement
# Vercel injecte généralement POSTGRES_URL ou DATABASE_URL
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")

# Fallback sur SQLite pour le développement local si aucune URL n'est trouvée
if not SQLALCHEMY_DATABASE_URL:
    SQLALCHEMY_DATABASE_URL = "sqlite:///./jetwatch.db"

# Pour PostgreSQL, on retire l'argument check_same_thread (spécifique à SQLite)
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    # Pour Neon/Postgres, on utilise l'URL telle quelle (psycopg2-binary est requis)
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

