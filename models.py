from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.orm import declarative_base

Base = declarative_base()

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
    co2_kg = Column(Float, nullable=True, default=None)
