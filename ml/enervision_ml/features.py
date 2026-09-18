"""Construction des features pour le modele de consommation.

Module partage entre l'entrainement et le futur scoring (cf. `docs/ML-START.md`) : la fonction
qui construit les features doit rester strictement identique des deux cotes, sous peine de
"train/serve skew" silencieux (le modele recoit en production des features qui ne ressemblent
plus a ce qu'il a appris).
"""

from collections.abc import Sequence

import pandas as pd

# Cible de l'entrainement : consommation en kWh, jamais consumption_kw (absent des lectures
# historiques CSV, cf. `apps/backend/app/etl/historical_import.py`).
TARGET_COLUMN = "consumption_kwh"

# Decalages horaires utilises pour les lags et moyennes glissantes : une heure avant, un jour
# avant (meme heure), une semaine avant (meme heure, meme jour) - saisonnalites usuelles d'une
# consommation energetique horaire.
LAG_HOURS: Sequence[int] = (1, 24, 168)
ROLLING_WINDOWS_HOURS: Sequence[int] = (24, 168)

STATIC_FEATURE_COLUMNS: Sequence[str] = ("site_type", "capacity_kw")

CALENDAR_FEATURE_COLUMNS: Sequence[str] = (
    "hour",
    "day_of_week",
    "month",
    "is_weekend",
    "is_working_hours",
)

WEATHER_COLUMNS: Sequence[str] = (
    "temperature_celsius",
    "humidity_percent",
    "solar_irradiance_wm2",
)


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Construit la matrice de features a partir de lectures brutes triees par site.

    `frame` doit porter au minimum : `site_id`, `timestamp`, `consumption_kwh`,
    `is_working_hours`, les trois colonnes meteo, et les colonnes statiques de site
    (`site_type`, `capacity_kw`). Une ligne par `(site_id, timestamp)`, sans doublon.

    Piege : la meteo n'entre dans les features que decalee (lag/moyenne glissante), jamais a
    l'instant cible. A l'entrainement comme au scoring, la meteo au moment predit n'est pas une
    mesure mais une prevision que le projet n'a pas — l'utiliser telle quelle romprait le
    contrat entre entrainement et usage reel (la feature ne serait tout simplement plus
    disponible en production). Cf. debat d'architecture dans l'issue #89.
    """
    travail = frame.sort_values(["site_id", "timestamp"]).reset_index(drop=True)

    calendrier = _calendar_features(travail["timestamp"])
    decalees = _lagged_features(travail)

    features = pd.concat(
        [
            travail[["site_id", "timestamp"]],
            travail[list(STATIC_FEATURE_COLUMNS)],
            calendrier,
            travail[["is_working_hours"]],
            decalees,
            travail[[TARGET_COLUMN]],
        ],
        axis=1,
    )

    # `period_minutes` : resolution temporelle de la cible. Les lectures historiques sont toutes
    # au pas horaire (cf. `dataset_metadata.json`, `frequency: "1h""), donc une constante pour
    # l'instant. Exposee comme feature plutot que supposee implicitement, pour que le modele
    # puisse un jour apprendre sur d'autres resolutions sans reentrainement de zero.
    features["period_minutes"] = 60

    return features


def feature_columns() -> list[str]:
    """Liste ordonnee des colonnes d'entree du modele (hors identifiants et cible)."""
    lag_columns = [f"consumption_kwh_lag_{h}h" for h in LAG_HOURS]
    rolling_columns = [
        f"{colonne}_rolling_mean_{fenetre}h"
        for colonne in (TARGET_COLUMN, *WEATHER_COLUMNS)
        for fenetre in ROLLING_WINDOWS_HOURS
    ]
    weather_lag_columns = [f"{colonne}_lag_1h" for colonne in WEATHER_COLUMNS]

    return [
        *STATIC_FEATURE_COLUMNS,
        *CALENDAR_FEATURE_COLUMNS,
        "period_minutes",
        *lag_columns,
        *rolling_columns,
        *weather_lag_columns,
    ]


def _calendar_features(timestamps: pd.Series) -> pd.DataFrame:
    instants = pd.to_datetime(timestamps)

    return pd.DataFrame(
        {
            "hour": instants.dt.hour,
            "day_of_week": instants.dt.dayofweek,
            "month": instants.dt.month,
            "is_weekend": instants.dt.dayofweek.isin([5, 6]).astype(int),
        }
    )


def _lagged_features(travail: pd.DataFrame) -> pd.DataFrame:
    par_site = travail.groupby("site_id", sort=False)
    colonnes: dict[str, pd.Series] = {}

    for decalage in LAG_HOURS:
        colonnes[f"{TARGET_COLUMN}_lag_{decalage}h"] = par_site[TARGET_COLUMN].shift(decalage)

    for colonne in (TARGET_COLUMN, *WEATHER_COLUMNS):
        decale = par_site[colonne].shift(1)
        for fenetre in ROLLING_WINDOWS_HOURS:
            colonnes[f"{colonne}_rolling_mean_{fenetre}h"] = decale.groupby(
                travail["site_id"]
            ).transform(lambda serie, fenetre=fenetre: serie.rolling(fenetre, min_periods=1).mean())

    for colonne in WEATHER_COLUMNS:
        colonnes[f"{colonne}_lag_1h"] = par_site[colonne].shift(1)

    return pd.DataFrame(colonnes, index=travail.index)
