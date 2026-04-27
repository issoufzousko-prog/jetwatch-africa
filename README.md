# JETWATCH AFRICA

Outil de transparence pour suivre et analyser les vols des jets privés présidentiels africains via l'API gratuite OpenSky Network.

## Objectif
Générer des rapports mensuels avec :
- Nombre de vols et heures de vol totales
- Classification de chaque vol (diplomatique / sommet / personnel)
- Empreinte CO2 comparée au foyer moyen du pays concerné
- Classement des présidents par usage

## Installation
1. Installer les dépendances :
`pip install -r requirements.txt`

2. Lancer le serveur :
`uvicorn main:app --reload`

## Exemples
- **Côte d'Ivoire (TU-VAJ)** : Le code ICAO24 pour ce jet est `038f4a`.
