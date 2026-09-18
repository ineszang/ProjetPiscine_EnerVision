"""Chargement des donnees d'entrainement.

Deux chemins, qui doivent produire le meme schema de sortie (colonnes `site_id`, `timestamp`,
`consumption_kwh`, `temperature_celsius`, `humidity_percent`, `solar_irradiance_wm2`,
`is_working_hours`, `site_type`, `capacity_kw`), consomme ensuite par `enervision_ml.features` :

- `load_from_database` : le chemin cible decrit dans `docs/ML-START.md`, connexion PostgreSQL
  directe (`reading` + `site`), pas par l'API. C'est celui qu'utilisera le pipeline en
  production, une fois le role PostgreSQL dedie `enervision_ml` provisionne (dette assumee,
  documentee dans `CLAUDE.md` et l'ADR 0003 : pour l'instant, la meme chaine de connexion que le
  backend applicatif convient en developpement).
- `load_from_csv` : chemin de demarrage, tant que la base locale n'est pas peuplee. Lit
  directement `ml/data/all_sites_combined.csv` (jeu de donnees fourni pour le jalon J3, cf.
  issue #89), le meme fichier que celui consomme par
  `apps/backend/app/etl/historical_import.py`. `capacity_kw` n'existe pas dans ce CSV : la
  colonne est renvoyee a `NaN`, que LightGBM gere nativement comme valeur manquante.
"""

from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connectable

OUTPUT_COLUMNS = [
    "site_id",
    "timestamp",
    "consumption_kwh",
    "temperature_celsius",
    "humidity_percent",
    "solar_irradiance_wm2",
    "is_working_hours",
    "site_type",
    "capacity_kw",
]

_READING_QUERY = text(
    """
    SELECT
        r.site_id,
        r.timestamp,
        r.consumption_kwh,
        r.temperature_celsius,
        r.humidity_percent,
        r.solar_irradiance_wm2,
        r.is_working_hours,
        s.site_type,
        s.capacity_kw
    FROM reading r
    JOIN site s ON s.site_id = r.site_id
    ORDER BY r.site_id, r.timestamp
    """
)


def load_from_database(connection: Connectable) -> pd.DataFrame:
    """Lit l'historique complet `reading` + `site` depuis PostgreSQL."""
    frame = pd.read_sql(_READING_QUERY, connection)
    return frame[OUTPUT_COLUMNS]


def load_from_csv(csv_path: Path) -> pd.DataFrame:
    """Lit le jeu de donnees CSV historique (chemin de demarrage, hors base)."""
    frame = pd.read_csv(csv_path, parse_dates=["timestamp"])
    frame["capacity_kw"] = float("nan")
    frame["is_working_hours"] = frame["is_working_hours"].astype(bool)

    return frame[OUTPUT_COLUMNS]
