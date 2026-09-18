from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from enervision_ml.features import TARGET_COLUMN
from enervision_ml.score import (
    LAG_168H_COLUMN,
    ScoredSite,
    build_scoring_frame,
    model_reference,
    run_scoring,
    score,
    write_predictions,
)


def make_recent(
    site_id: str, *, heures: int, depart: datetime, valeur: float = 10.0
) -> pd.DataFrame:
    instants = [depart + timedelta(hours=h) for h in range(heures)]
    return pd.DataFrame(
        {
            "site_id": site_id,
            "timestamp": instants,
            TARGET_COLUMN: [valeur + h for h in range(heures)],
            "temperature_celsius": 15.0,
            "humidity_percent": 50.0,
            "solar_irradiance_wm2": 0.0,
            "is_working_hours": True,
            "site_type": "office",
            "capacity_kw": 100.0,
        }
    )


class FakeBooster:
    def __init__(self, valeur: float = 42.0) -> None:
        self.valeur = valeur
        self.appels: list[int] = []

    def predict(self, X: Any) -> list[float]:
        self.appels.append(len(X))
        return [self.valeur] * len(X)


class FakeConnection:
    def __init__(self) -> None:
        self.appels: list[tuple[Any, Any]] = []

    def execute(self, statement: Any, parameters: Any = None) -> None:
        self.appels.append((statement, parameters))


def test_build_scoring_frame_adds_one_row_per_site_one_hour_after_the_last_reading() -> None:
    depart = datetime(2026, 1, 1, tzinfo=UTC)
    recent = pd.concat(
        [
            make_recent("site-a", heures=200, depart=depart),
            make_recent("site-b", heures=200, depart=depart),
        ],
        ignore_index=True,
    )

    scoring_frame = build_scoring_frame(recent)

    assert set(scoring_frame["site_id"]) == {"site-a", "site-b"}
    derniere_lecture = depart + timedelta(hours=199)
    assert (scoring_frame["timestamp"] == derniere_lecture + timedelta(hours=1)).all()


def test_build_scoring_frame_computes_lags_from_real_history() -> None:
    depart = datetime(2026, 1, 1, tzinfo=UTC)
    recent = make_recent("site-a", heures=200, depart=depart)

    scoring_frame = build_scoring_frame(recent)

    ligne = scoring_frame.iloc[0]
    # La cible future n'existe pas : le lag d'1h doit valoir la toute derniere valeur reelle.
    assert ligne[f"{TARGET_COLUMN}_lag_1h"] == recent[TARGET_COLUMN].iloc[-1]


def test_build_scoring_frame_flags_insufficient_history_under_168_hours() -> None:
    depart = datetime(2026, 1, 1, tzinfo=UTC)
    recent = make_recent("site-a", heures=100, depart=depart)

    scoring_frame = build_scoring_frame(recent)

    assert pd.isna(scoring_frame.iloc[0][LAG_168H_COLUMN])


def test_build_scoring_frame_accepts_a_full_week_of_history() -> None:
    depart = datetime(2026, 1, 1, tzinfo=UTC)
    recent = make_recent("site-a", heures=169, depart=depart)

    scoring_frame = build_scoring_frame(recent)

    assert not pd.isna(scoring_frame.iloc[0][LAG_168H_COLUMN])


def test_build_scoring_frame_filters_to_a_single_site() -> None:
    depart = datetime(2026, 1, 1, tzinfo=UTC)
    recent = pd.concat(
        [
            make_recent("site-a", heures=200, depart=depart),
            make_recent("site-b", heures=200, depart=depart),
        ],
        ignore_index=True,
    )

    scoring_frame = build_scoring_frame(recent, site_id="site-a")

    assert scoring_frame["site_id"].tolist() == ["site-a"]


def test_build_scoring_frame_returns_empty_when_there_is_no_recent_reading() -> None:
    recent = make_recent("site-a", heures=0, depart=datetime(2026, 1, 1, tzinfo=UTC))

    scoring_frame = build_scoring_frame(recent)

    assert scoring_frame.empty


def test_score_marks_insufficient_history_without_calling_the_model() -> None:
    depart = datetime(2026, 1, 1, tzinfo=UTC)
    scoring_frame = build_scoring_frame(make_recent("site-a", heures=100, depart=depart))
    booster = FakeBooster()

    resultats = score(booster, scoring_frame)  # type: ignore[arg-type]

    assert resultats == [
        ScoredSite(
            site_id="site-a",
            target_at=resultats[0].target_at,
            status="insufficient_data",
            predicted_value=None,
            failure_reason=resultats[0].failure_reason,
        )
    ]
    assert booster.appels == []


def test_score_predicts_when_history_is_sufficient() -> None:
    depart = datetime(2026, 1, 1, tzinfo=UTC)
    scoring_frame = build_scoring_frame(make_recent("site-a", heures=200, depart=depart))
    booster = FakeBooster(valeur=99.5)

    resultats = score(booster, scoring_frame)  # type: ignore[arg-type]

    assert len(resultats) == 1
    assert resultats[0].status == "available"
    assert resultats[0].predicted_value == 99.5
    assert resultats[0].failure_reason is None
    assert booster.appels == [1]


def test_write_predictions_does_nothing_when_there_is_nothing_to_write() -> None:
    connection = FakeConnection()

    write_predictions(connection, [], reference="lightgbm-test")  # type: ignore[arg-type]

    assert connection.appels == []


def test_write_predictions_sends_one_row_per_result() -> None:
    connection = FakeConnection()
    resultats = [
        ScoredSite("site-a", datetime(2026, 1, 1, tzinfo=UTC), "available", 42.0, None),
        ScoredSite(
            "site-b",
            datetime(2026, 1, 1, tzinfo=UTC),
            "insufficient_data",
            None,
            "pas assez d'historique",
        ),
    ]

    write_predictions(connection, resultats, reference="lightgbm-test")  # type: ignore[arg-type]

    assert len(connection.appels) == 1
    _, lignes = connection.appels[0]
    assert len(lignes) == 2
    assert lignes[0]["model_reference"] == "lightgbm-test"
    assert lignes[0]["target_metric"] == "consumption_kwh"
    assert lignes[0]["period_minutes"] == 60


def test_model_reference_is_stable_for_the_same_file_content(tmp_path: Path) -> None:
    model_path = tmp_path / "model.txt"
    model_path.write_bytes(b"contenu-du-modele")

    assert model_reference(model_path) == model_reference(model_path)


def test_model_reference_changes_with_the_file_content(tmp_path: Path) -> None:
    premier = tmp_path / "model-a.txt"
    premier.write_bytes(b"version-1")
    second = tmp_path / "model-b.txt"
    second.write_bytes(b"version-2")

    assert model_reference(premier) != model_reference(second)


def test_run_scoring_in_csv_mode_scores_without_touching_a_database(tmp_path: Path) -> None:
    depart = datetime(2026, 1, 1, tzinfo=UTC)
    frame = pd.concat(
        [
            make_recent("site-a", heures=400, depart=depart),
            make_recent("site-b", heures=400, depart=depart),
        ],
        ignore_index=True,
    )
    csv_path = tmp_path / "recent.csv"
    frame.to_csv(csv_path, index=False)

    model_path = tmp_path / "model.txt"
    model_path.write_bytes(b"peu importe le contenu pour ce test")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "enervision_ml.score.lgb.Booster", lambda model_file: FakeBooster(valeur=7.0)
        )

        resultats = run_scoring(model_path=model_path, csv_path=csv_path)

    assert {r.site_id for r in resultats} == {"site-a", "site-b"}
    assert all(r.status == "available" for r in resultats)
    assert all(r.predicted_value == 7.0 for r in resultats)
