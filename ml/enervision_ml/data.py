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

from datetime import datetime
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

NUMERIC_COLUMNS = [
    "consumption_kwh",
    "temperature_celsius",
    "humidity_percent",
    "solar_irradiance_wm2",
    "capacity_kw",
]

# Piege : `is_working_hours` est nullable et entre dans les features. Toujours `float64`, jamais
# `bool` : `astype(bool)` ferait un `True` d'une absence, et les deux chargeurs divergeraient.
FLAG_COLUMNS = ["is_working_hours"]

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


_RECENT_READING_QUERY = text(
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
    WHERE r.timestamp >= :since AND r.timestamp <= :until
    ORDER BY r.site_id, r.timestamp
    """
)


def load_from_database(connection: Connectable) -> pd.DataFrame:
    """Lit l'historique complet `reading` + `site` depuis PostgreSQL. Entrainement seulement :
    le scoring n'a besoin que d'une fenetre recente, cf. `load_recent_from_database`.
    """
    frame = pd.read_sql(_READING_QUERY, connection)
    return _typer(frame[OUTPUT_COLUMNS])


def load_recent_from_database(
    connection: Connectable, *, since: datetime, until: datetime
) -> pd.DataFrame:
    """Lit `reading` + `site` sur la fenetre `[since, until]`, pour le scoring.

    Piege evite cote bas : un `SELECT` sans borne sur l'hypertable complete juste pour scorer le
    prochain pas horaire serait la meme erreur que celle corrigee sur `GET /readings` (fenetre non
    plafonnee sur une table pouvant porter des annees d'historique).

    Piege evite cote haut : `until` est obligatoire, et c'est ce qui donne son sens a `--now`.
    Sans lui, `build_scoring_frame` repartait de la derniere lecture de toute la table quel que
    soit l'instant demande, donc `target_at` valait toujours "fin du jeu + 1h" et l'age de la
    derniere lecture devenait negatif sans que rien ne le signale.
    """
    frame = pd.read_sql(_RECENT_READING_QUERY, connection, params={"since": since, "until": until})
    return _typer(frame[OUTPUT_COLUMNS])


def load_from_csv(csv_path: Path) -> pd.DataFrame:
    """Lit le jeu de donnees CSV historique (chemin de demarrage, hors base).

    `is_working_hours` passe par `_typer` comme le chemin base, et non par un `astype(bool)` : le
    fichier livre porte cette colonne en `0`/`1`, donc une case vide arrive en `NaN` et `astype`
    la rendrait `True` sans rien signaler. Les deux chargeurs rendent ainsi le meme schema, ce que
    `docs/ML-START.md` promet.
    """
    frame = pd.read_csv(csv_path, parse_dates=["timestamp"])
    frame["capacity_kw"] = float("nan")

    return _typer(frame[OUTPUT_COLUMNS])


def _typer(frame: pd.DataFrame) -> pd.DataFrame:
    """Force le typage numerique attendu par LightGBM.

    Piege reel, pas theorique : `site.capacity_kw` n'est peuple par aucun pipeline d'ingestion
    aujourd'hui (`historical_import.py` ne pose que `site_type`/`site_name`). Une colonne
    entierement `NULL` revient de `pd.read_sql` en dtype `object` plutot que `float64`, ce que
    LightGBM refuse ("pandas dtypes must be int, float or bool"). `pd.to_numeric` corrige aussi
    n'importe quelle autre colonne mesuree entierement absente sur une fenetre de scoring, pas
    seulement `capacity_kw`.

    Les colonnes de `FLAG_COLUMNS` sont en outre ramenees a `float64` : ce sont des drapeaux
    nullables, et c'est le seul dtype qui survive a l'absence sans inventer de valeur. Sans cela,
    le meme chargeur rendrait `bool`, `int64` ou `float64` selon le contenu de la fenetre lue.

    Piege additionnel : `NUMERIC_COLUMNS` inclut `consumption_kwh`, la cible du modele, pas
    seulement des variables explicatives. Une valeur non numerique y devient donc silencieusement
    `NaN` aussi bien a l'entrainement (ou `train.py` l'exclura ensuite via son `dropna`) qu'au
    scoring -- ce n'est pas un effet de bord limite aux colonnes mesurees.
    """
    typee = frame.copy()
    for colonne in NUMERIC_COLUMNS:
        typee[colonne] = pd.to_numeric(typee[colonne], errors="coerce")
    for colonne in FLAG_COLUMNS:
        typee[colonne] = pd.to_numeric(typee[colonne], errors="coerce").astype("float64")
    return typee
