from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Connection, Row, text
from sqlalchemy.exc import IntegrityError

from enervision_ml.score import (
    INSUFFICIENT_DATA_REASON,
    LOOKBACK,
    MAX_STALENESS,
    ScoredSite,
    model_reference,
    run_scoring,
    write_predictions,
)
from tests.conftest import ANCRAGE, Parc, insere_site

pytestmark = pytest.mark.integration

REFERENCE = "lightgbm-000000000000"

_SELECT = text(
    """
    SELECT target_at, target_metric, period_minutes, predicted_value,
           model_reference, status, failure_reason
    FROM prediction
    WHERE site_id = :site_id
    ORDER BY prediction_id
    """
)


def lignes(connexion: Connection, site_id: str) -> list[Row[Any]]:
    return list(connexion.execute(_SELECT, {"site_id": site_id}))


def disponible(
    site_id: str,
    *,
    target_at: datetime = ANCRAGE,
    predicted_value: float | None = 12.5,
) -> ScoredSite:
    return ScoredSite(
        site_id=site_id,
        target_at=target_at,
        status="available",
        predicted_value=predicted_value,
        failure_reason=None,
    )


def test_write_predictions_inserts_one_row_per_scored_site(connexion_ml: Connection) -> None:
    premier = insere_site(connexion_ml)
    second = insere_site(connexion_ml)

    write_predictions(connexion_ml, [disponible(premier), disponible(second)], reference=REFERENCE)

    assert len(lignes(connexion_ml, premier)) == 1
    assert len(lignes(connexion_ml, second)) == 1


def test_write_predictions_stores_the_model_reference_and_the_hourly_period(
    connexion_ml: Connection,
) -> None:
    site_id = insere_site(connexion_ml)

    write_predictions(connexion_ml, [disponible(site_id)], reference=REFERENCE)

    ligne = lignes(connexion_ml, site_id)[0]
    assert ligne.model_reference == REFERENCE
    assert ligne.target_metric == "consumption_kwh"
    assert ligne.period_minutes == 60


def test_write_predictions_stacks_a_second_run_instead_of_overwriting_the_first(
    connexion_ml: Connection,
) -> None:
    site_id = insere_site(connexion_ml)

    write_predictions(
        connexion_ml, [disponible(site_id, predicted_value=10.0)], reference=REFERENCE
    )
    write_predictions(
        connexion_ml, [disponible(site_id, predicted_value=20.0)], reference=REFERENCE
    )

    assert [ligne.predicted_value for ligne in lignes(connexion_ml, site_id)] == [10.0, 20.0]


def test_write_predictions_writes_nothing_when_no_site_was_scored(
    connexion_ml: Connection,
) -> None:
    site_id = insere_site(connexion_ml)

    write_predictions(connexion_ml, [], reference=REFERENCE)

    assert lignes(connexion_ml, site_id) == []


def test_write_predictions_rejects_an_available_row_without_a_predicted_value(
    connexion_ml: Connection,
) -> None:
    site_id = insere_site(connexion_ml)

    with pytest.raises(IntegrityError, match="ck_prediction_status"):
        write_predictions(
            connexion_ml, [disponible(site_id, predicted_value=None)], reference=REFERENCE
        )


def test_write_predictions_rejects_an_insufficient_data_row_carrying_a_value(
    connexion_ml: Connection,
) -> None:
    site_id = insere_site(connexion_ml)
    incoherent = ScoredSite(
        site_id=site_id,
        target_at=ANCRAGE,
        status="insufficient_data",
        predicted_value=12.5,
        failure_reason=INSUFFICIENT_DATA_REASON,
    )

    with pytest.raises(IntegrityError, match="ck_prediction_status"):
        write_predictions(connexion_ml, [incoherent], reference=REFERENCE)


def test_write_predictions_rejects_a_prediction_for_an_unknown_site(
    connexion_ml: Connection,
) -> None:
    with pytest.raises(IntegrityError, match="fk_prediction_site"):
        write_predictions(connexion_ml, [disponible("SITE-INCONNU")], reference=REFERENCE)


def test_run_scoring_writes_an_available_prediction_for_a_site_with_a_full_week(
    parc: Parc, modele_jetable: Path
) -> None:
    site_id = parc.site()
    parc.lectures(site_id, heures=200, fin=ANCRAGE)

    run_scoring(model_path=modele_jetable, now=ANCRAGE)

    ligne = parc.predictions_ecrites(site_id)[0]
    assert ligne.status == "available"
    assert ligne.predicted_value is not None
    assert ligne.target_at == ANCRAGE + timedelta(hours=1)


def test_run_scoring_writes_insufficient_data_when_the_weekly_lag_is_missing(
    parc: Parc, modele_jetable: Path
) -> None:
    site_id = parc.site()
    parc.lectures(site_id, heures=100, fin=ANCRAGE)

    run_scoring(model_path=modele_jetable, now=ANCRAGE)

    ligne = parc.predictions_ecrites(site_id)[0]
    assert ligne.status == "insufficient_data"
    assert ligne.predicted_value is None
    assert ligne.failure_reason == INSUFFICIENT_DATA_REASON


def test_run_scoring_writes_a_staleness_reason_when_the_last_reading_is_too_old(
    parc: Parc, modele_jetable: Path
) -> None:
    site_id = parc.site()
    parc.lectures(site_id, heures=200, fin=ANCRAGE)

    run_scoring(model_path=modele_jetable, now=ANCRAGE + MAX_STALENESS + timedelta(hours=1))

    ligne = parc.predictions_ecrites(site_id)[0]
    assert ligne.status == "insufficient_data"
    assert ligne.failure_reason != INSUFFICIENT_DATA_REASON


def test_run_scoring_writes_nothing_when_every_reading_is_older_than_the_window(
    parc: Parc, modele_jetable: Path
) -> None:
    site_id = parc.site()
    parc.lectures(site_id, heures=200, fin=ANCRAGE)

    run_scoring(model_path=modele_jetable, now=ANCRAGE + LOOKBACK + timedelta(days=1))

    assert parc.predictions_ecrites(site_id) == []


def test_run_scoring_only_writes_the_site_that_was_requested(
    parc: Parc, modele_jetable: Path
) -> None:
    demande = parc.site()
    ignore = parc.site()
    parc.lectures(demande, heures=200, fin=ANCRAGE)
    parc.lectures(ignore, heures=200, fin=ANCRAGE)

    run_scoring(model_path=modele_jetable, site_id=demande, now=ANCRAGE)

    assert len(parc.predictions_ecrites(demande)) == 1
    assert parc.predictions_ecrites(ignore) == []


def test_run_scoring_uses_the_model_file_hash_as_model_reference(
    parc: Parc, modele_jetable: Path
) -> None:
    site_id = parc.site()
    parc.lectures(site_id, heures=200, fin=ANCRAGE)

    run_scoring(model_path=modele_jetable, now=ANCRAGE)

    ligne = parc.predictions_ecrites(site_id)[0]
    assert ligne.model_reference == model_reference(modele_jetable)


def test_run_scoring_appends_a_second_row_when_it_runs_twice(
    parc: Parc, modele_jetable: Path
) -> None:
    site_id = parc.site()
    parc.lectures(site_id, heures=200, fin=ANCRAGE)

    run_scoring(model_path=modele_jetable, now=ANCRAGE)
    run_scoring(model_path=modele_jetable, now=ANCRAGE)

    ecrites = parc.predictions_ecrites(site_id)
    assert len(ecrites) == 2
    assert ecrites[0].target_at == ecrites[1].target_at
