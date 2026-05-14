import math
from typing import List, Dict, Any

# Liste des cibles potentielles mondiales (capitales, centres financiers, médicaux)
TARGET_CITIES = [
    {"name": "Paris", "lat": 48.8566, "lon": 2.3522, "country": "France", "type": "Diplomatie/Immobilier"},
    {"name": "Genève", "lat": 46.2044, "lon": 6.1432, "country": "Suisse", "type": "Banque/Médical"},
    {"name": "Londres", "lat": 51.5074, "lon": -0.1278, "country": "Royaume-Uni", "type": "Finance/Immobilier"},
    {"name": "Dubaï", "lat": 25.2048, "lon": 55.2708, "country": "Émirats Arabes Unis", "type": "Finance/Loisir"},
    {"name": "New York", "lat": 40.7128, "lon": -74.0060, "country": "États-Unis", "type": "Diplomatie (ONU)"},
    {"name": "Washington D.C.", "lat": 38.9072, "lon": -77.0369, "country": "États-Unis", "type": "Diplomatie"},
    {"name": "Moscou", "lat": 55.7558, "lon": 37.6173, "country": "Russie", "type": "Diplomatie"},
    {"name": "Pékin", "lat": 39.9042, "lon": 116.4074, "country": "Chine", "type": "Diplomatie/Commerce"},
    {"name": "Istanbul", "lat": 41.0082, "lon": 28.9784, "country": "Turquie", "type": "Transit/Diplomatie"},
    {"name": "Riyad", "lat": 24.7136, "lon": 46.6753, "country": "Arabie Saoudite", "type": "Diplomatie/Finance"},
    {"name": "Johannesburg", "lat": -26.2041, "lon": 28.0473, "country": "Afrique du Sud", "type": "Médical/Commerce"},
    {"name": "Marrakech", "lat": 31.6295, "lon": -8.0365, "country": "Maroc", "type": "Loisir/Sommet"},
    {"name": "Addis-Abeba", "lat": 9.0320, "lon": 38.7482, "country": "Éthiopie", "type": "Diplomatie (UA)"},
    {"name": "Malabo", "lat": 3.7504, "lon": 8.7865, "country": "Guinée équatoriale", "type": "Régional"}
]

def calculate_initial_compass_bearing(pointA: tuple, pointB: tuple) -> float:
    """
    Calcule le cap (bearing) initial pour aller du pointA au pointB.
    pointA et pointB sont des tuples (latitude, longitude) en degrés décimaux.
    """
    if (type(pointA) != tuple) or (type(pointB) != tuple):
        raise TypeError("Seuls les tuples sont supportés comme arguments")

    lat1 = math.radians(pointA[0])
    lat2 = math.radians(pointB[0])
    diffLong = math.radians(pointB[1] - pointA[1])

    x = math.sin(diffLong) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(diffLong))

    initial_bearing = math.atan2(x, y)
    
    # Normalisation entre 0° et 360°
    initial_bearing = math.degrees(initial_bearing)
    compass_bearing = (initial_bearing + 360) % 360

    return compass_bearing

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcule la distance orthodromique entre deux points sur Terre en km.
    """
    R = 6371.0 # Rayon de la terre en km
    
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

def get_predictions(current_lat: float, current_lon: float, current_track: float) -> List[Dict[str, Any]]:
    """
    Détermine quelles cibles se trouvent dans le cône de projection de l'avion.
    """
    predictions = []
    CONE_ANGLE_THRESHOLD = 20.0 # +/- 20 degrés de tolérance
    
    if current_track is None:
        return predictions

    plane_pos = (current_lat, current_lon)

    for city in TARGET_CITIES:
        city_pos = (city["lat"], city["lon"])
        
        # 1. Calculer la distance
        distance_km = haversine_distance(plane_pos[0], plane_pos[1], city_pos[0], city_pos[1])
        
        # Ignorer les villes trop proches (< 100km) ou absurdes (> 12000km)
        if distance_km < 100 or distance_km > 12000:
            continue
            
        # 2. Calculer le cap nécessaire pour atteindre la ville depuis l'avion
        bearing_to_city = calculate_initial_compass_bearing(plane_pos, city_pos)
        
        # 3. Calculer la différence entre le cap actuel et le cap nécessaire
        # Il faut gérer le passage par 360 (ex: track 350 et bearing 10 => diff 20)
        diff = abs(current_track - bearing_to_city)
        if diff > 180:
            diff = 360 - diff
            
        # 4. Si la ville est dans le cône, on l'ajoute
        if diff <= CONE_ANGLE_THRESHOLD:
            # Calculer une probabilité basique mathématique basée sur l'alignement
            # Plus la diff est proche de 0, plus la probabilité est haute (max 95%)
            # C'est une probabilité géométrique qui sera ensuite pondérée par l'OSINT (LLM)
            alignment_score = 1.0 - (diff / CONE_ANGLE_THRESHOLD) # 1.0 si alignement parfait
            base_prob = round((alignment_score * 80) + 10) # Probabilité entre 10% et 90%
            
            predictions.append({
                "city": city["name"],
                "country": city["country"],
                "type": city["type"],
                "lat": city["lat"],
                "lon": city["lon"],
                "distance_km": round(distance_km),
                "probability": base_prob
            })
            
    # Trier par probabilité décroissante
    predictions.sort(key=lambda x: x["probability"], reverse=True)
    return predictions
