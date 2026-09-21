"""Baseline de persistance saisonniere, la barre a depasser pour justifier LightGBM.

Predit la consommation de l'heure cible par celle de la meme heure, une semaine avant
(`consumption_kwh_lag_168h`) : une consommation energetique horaire est dominee par le cycle
hebdomadaire (jours ouvres contre week-end), donc ce naif-la est deja un concurrent serieux.
"""

import pandas as pd

from enervision_ml.features import TARGET_COLUMN

SEASONAL_LAG_COLUMN = f"{TARGET_COLUMN}_lag_168h"


def seasonal_persistence_predictions(features: pd.DataFrame) -> pd.Series:
    return features[SEASONAL_LAG_COLUMN]
