from datetime import UTC, datetime, timedelta
from typing import cast

import pandas as pd

from enervision_ml.features import TARGET_COLUMN, build_features, feature_columns


def make_site_reading(
    site_id: str, *, heures: int, depart: datetime, valeur: float = 10.0
) -> pd.DataFrame:
    instants = [depart + timedelta(hours=h) for h in range(heures)]
    return pd.DataFrame(
        {
            "site_id": site_id,
            "timestamp": instants,
            TARGET_COLUMN: [valeur + h for h in range(heures)],
            "temperature_celsius": [15.0] * heures,
            "humidity_percent": [50.0] * heures,
            "solar_irradiance_wm2": [0.0] * heures,
            "is_working_hours": [True] * heures,
            "site_type": "office",
            "capacity_kw": 100.0,
        }
    )


def two_site_frame(heures: int = 200) -> pd.DataFrame:
    depart = datetime(2026, 1, 1, tzinfo=UTC)
    return pd.concat(
        [
            make_site_reading("site-a", heures=heures, depart=depart, valeur=10.0),
            make_site_reading("site-b", heures=heures, depart=depart, valeur=1000.0),
        ],
        ignore_index=True,
    )


def test_build_features_returns_every_declared_feature_column() -> None:
    features = build_features(two_site_frame())

    manquantes = set(feature_columns()) - set(features.columns)

    assert manquantes == set()


def test_build_features_sets_a_constant_period_minutes() -> None:
    features = build_features(two_site_frame())

    assert (features["period_minutes"] == 60).all()


def test_build_features_lag_1h_matches_the_previous_hour_of_the_same_site() -> None:
    features = build_features(two_site_frame(heures=200))
    site_a = features[features["site_id"] == "site-a"].reset_index(drop=True)

    assert site_a.loc[10, f"{TARGET_COLUMN}_lag_1h"] == site_a.loc[9, TARGET_COLUMN]


def test_build_features_lag_168h_is_nan_before_a_full_week_of_history() -> None:
    features = build_features(two_site_frame(heures=200))
    site_a = features[features["site_id"] == "site-a"].reset_index(drop=True)

    assert pd.isna(site_a.loc[100, f"{TARGET_COLUMN}_lag_168h"])
    assert not pd.isna(site_a.loc[168, f"{TARGET_COLUMN}_lag_168h"])


def test_build_features_never_leaks_lags_across_sites() -> None:
    # site-b demarre a 1000 : si un lag de site-a s'y glissait, la valeur sortirait de son
    # echelle (10, 11, 12, ...).
    features = build_features(two_site_frame(heures=200))
    site_b = features[features["site_id"] == "site-b"].reset_index(drop=True)

    assert cast(float, site_b.loc[5, f"{TARGET_COLUMN}_lag_1h"]) >= 1000.0


def test_build_features_rolling_mean_excludes_the_current_hour() -> None:
    # Valeurs constantes sauf la derniere ligne : si la moyenne glissante incluait l'heure
    # courante, la constante ne resterait pas stable jusqu'au bout.
    depart = datetime(2026, 1, 1, tzinfo=UTC)
    frame = make_site_reading("site-a", heures=200, depart=depart, valeur=10.0)
    frame[TARGET_COLUMN] = 10.0
    frame.loc[frame.index[-1], TARGET_COLUMN] = 10_000.0

    features = build_features(frame).reset_index(drop=True)

    assert features.loc[len(features) - 1, f"{TARGET_COLUMN}_rolling_mean_24h"] == 10.0


def test_build_features_computes_calendar_fields_from_the_timestamp() -> None:
    depart = datetime(2026, 1, 3, 6, tzinfo=UTC)  # un samedi, 6h
    features = build_features(make_site_reading("site-a", heures=1, depart=depart))

    assert features.loc[0, "hour"] == 6
    assert features.loc[0, "day_of_week"] == 5
    assert features.loc[0, "is_weekend"] == 1
