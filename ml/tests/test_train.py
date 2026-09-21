from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from enervision_ml.features import TARGET_COLUMN, build_features, feature_columns
from enervision_ml.train import chronological_split, prepare_dataset, train


def make_frame(site_id: str, *, heures: int, depart: datetime) -> pd.DataFrame:
    instants = [depart + timedelta(hours=h) for h in range(heures)]
    rng = np.random.default_rng(42)

    return pd.DataFrame(
        {
            "site_id": site_id,
            "timestamp": instants,
            TARGET_COLUMN: 100.0 + 10.0 * np.sin(np.arange(heures) / 24) + rng.normal(0, 1, heures),
            "temperature_celsius": 15.0,
            "humidity_percent": 50.0,
            "solar_irradiance_wm2": 0.0,
            "is_working_hours": True,
            "site_type": "office",
            "capacity_kw": 100.0,
        }
    )


def test_chronological_split_puts_the_most_recent_rows_in_validation() -> None:
    depart = datetime(2026, 1, 1, tzinfo=UTC)
    features = make_frame("site-a", heures=200, depart=depart)

    entrainement, validation = chronological_split(features, test_fraction=0.2)

    assert entrainement["timestamp"].max() < validation["timestamp"].min()
    # La coupure vient d'un quantile sur les dates : une approximation du taux demande, pas un
    # decompte exact de lignes.
    assert abs(len(validation) - 0.2 * len(features)) <= 2


def test_prepare_dataset_types_site_type_as_a_pandas_category() -> None:
    depart = datetime(2026, 1, 1, tzinfo=UTC)
    features = build_features(make_frame("site-a", heures=200, depart=depart))

    X, y = prepare_dataset(features, feature_columns())

    assert X["site_type"].dtype.name == "category"
    assert y.name == TARGET_COLUMN


def test_train_runs_end_to_end_on_synthetic_data_and_beats_a_dummy_baseline(
    tmp_path: Path,
) -> None:
    depart = datetime(2026, 1, 1, tzinfo=UTC)
    frame = pd.concat(
        [
            make_frame("site-a", heures=400, depart=depart),
            make_frame("site-b", heures=400, depart=depart),
        ],
        ignore_index=True,
    )
    csv_path = tmp_path / "synthetic.csv"
    frame.to_csv(csv_path, index=False)

    model_metrics, baseline_metrics = train(
        csv_path=csv_path,
        model_output=tmp_path / "model.txt",
        test_fraction=0.2,
        tracking_uri=f"sqlite:///{tmp_path / 'mlflow.db'}",
    )

    assert (tmp_path / "model.txt").exists()
    assert model_metrics["n_observations"] > 0
    assert model_metrics["mae"] >= 0
    assert baseline_metrics["n_observations"] == model_metrics["n_observations"]
    assert model_metrics["mae"] < baseline_metrics["mae"]

def test_train_raises_when_the_validation_window_is_empty(tmp_path: Path) -> None:
    depart = datetime(2026, 1, 1, tzinfo=UTC)
    frame = make_frame("site-a", heures=50, depart=depart)  # trop court pour un lag de 168h
    csv_path = tmp_path / "trop_court.csv"
    frame.to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match="Fenetre d'entrainement ou de validation vide"):
        train(
            csv_path=csv_path,
            model_output=tmp_path / "model.txt",
            test_fraction=0.2,
            tracking_uri=f"sqlite:///{tmp_path / 'mlflow.db'}",
        )
