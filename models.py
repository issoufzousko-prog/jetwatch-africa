import uuid
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    provider = Column(String, nullable=False) # 'google' or 'github'
    provider_id = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    role = Column(String, default="user") # "user", "admin"
    last_login = Column(Integer, nullable=True) # Unix timestamp

class Target(Base):
    __tablename__ = "targets"
    
    id = Column(Integer, primary_key=True, index=True)
    pays = Column(String, unique=True, index=True, nullable=False) # Agit comme identifiant unique
    dirigeant = Column(String, nullable=True)
    type_regime = Column(String, nullable=True)
    photo_url = Column(String, nullable=True)
    
    # Un "Target" (Pays/VIP) possède plusieurs "TargetFleet" (Jets)
    fleet = relationship("TargetFleet", back_populates="target", cascade="all, delete-orphan")

class TargetFleet(Base):
    __tablename__ = "target_fleets"
    
    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("targets.id"), index=True)
    icao24 = Column(String, index=True, nullable=False)
    tail_number = Column(String, nullable=True)
    description = Column(String, nullable=True)
    verifie = Column(Boolean, default=True)
    
    target = relationship("Target", back_populates="fleet")

class Flight(Base):
    __tablename__ = "flights"

    id = Column(Integer, primary_key=True, index=True)
    icao24 = Column(String, index=True)
    callsign = Column(String)
    departure_airport = Column(String)
    arrival_airport = Column(String)
    departure_time = Column(Integer) # Timestamp Unix
    arrival_time = Column(Integer)   # Timestamp Unix
    duration_minutes = Column(Float)
    classification = Column(String, nullable=True, default=None)
    classification_details = Column(String, nullable=True, default=None)  # JSON complet de la classification LLM
    co2_kg = Column(Float, nullable=True, default=None)
    investigation_report = Column(String, nullable=True, default=None)  # Rapport détective (markdown)
    knowledge_graph = Column(String, nullable=True, default=None)       # Graphe sérialisé (JSON)
    risk_score = Column(Float, nullable=True, default=None)             # Score de risque 0-10

    # Relation avec les positions (historique GPS)
    positions = relationship("FlightPosition", back_populates="flight", cascade="all, delete-orphan")

class FlightPosition(Base):
    __tablename__ = "flight_positions"

    id = Column(Integer, primary_key=True, index=True)
    flight_id = Column(Integer, ForeignKey("flights.id"), index=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    alt_baro = Column(Float, nullable=True) # Altitude en pieds
    gs = Column(Float, nullable=True)       # Vitesse au sol (noeuds)
    track = Column(Float, nullable=True)    # Cap (degrés)
    timestamp = Column(Integer, nullable=False) # Moment du relevé (Unix)

    flight = relationship("Flight", back_populates="positions")