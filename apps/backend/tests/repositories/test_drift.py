from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ClauseElement

from app.repositories.drift import (
    DriftRepository,
    NouveauRapportDerive,
    _lectures_retenues,
    _predictions_retenues,
)
from tests.repositories.test_prediction import creer_prediction
from tests.repositories.test_reading import creer_lecture
from tests.repositories.test_site import creer as creer_site

DEBUT = datetime(2026, 9, 15, tzinfo=UTC)
FIN = datetime(2026, 9, 22, tzinfo=UTC)
CIBLE = datetime(2026, 9, 16, 12, tzinfo=UTC)


def sql(requete: ClauseElement) -> str:
    return str(requete.compile(dialect=postgresql.dialect()))  # type: ignore[no-untyped-call]


def rapport(**remplacements: object) -> NouveauRapportDerive:
    defauts: dict[str, object] = {
        "site_id": None,
        "window_start": DEBUT,
        "window_end": FIN,
        "reference_start": None,
        "reference_end": None,
        "n_observations": 10,
        "mae": 1.0,
        "mape": 5.0,
        "bias": 0.1,
        "reference_mae": None,
        "coverage_ratio": 1.0,
        "insufficient_data_ratio": 0.0,
        "model_references": ["lightgbm-aaa"],
        "status": "stable",
        "reason": None,
    }
    return NouveauRapportDerive(**{**defauts, **remplacements})  # type: ignore[arg-type]


def test_predictions_keep_one_row_per_site_and_target_in_sql() -> None:
    requete = sql(_predictions_retenues(debut=DEBUT, fin=FIN, site_id=None).element)

    assert "DISTINCT ON (prediction.site_id, prediction.target_at)" in requete
    assert "prediction.prediction_id DESC" in requete


def test_readings_keep_one_row_per_site_and_instant_in_sql() -> None:
    requete = sql(_lectures_retenues(debut=DEBUT, fin=FIN, site_id=None).element)

    assert "DISTINCT ON (reading.site_id, reading.timestamp)" in requete
    assert "reading.reading_id DESC" in requete


def test_predictions_restrict_themselves_to_the_requested_site_in_sql() -> None:
    requete = sql(_predictions_retenues(debut=DEBUT, fin=FIN, site_id="SITE001").element)

    assert requete.count("prediction.site_id = ") == 1


def test_readings_ignore_a_missing_consumption_in_sql() -> None:
    requete = sql(_lectures_retenues(debut=DEBUT, fin=FIN, site_id=None).element)

    assert "reading.consumption_kwh IS NOT NULL" in requete


@pytest.mark.integration
async def test_repository_pairs_a_prediction_with_the_reading_of_the_same_instant(
    session: AsyncSession,
) -> None:
    site = await creer_site(session)
    await creer_prediction(session, site_id=site.site_id, target_at=CIBLE, predicted_value=12.0)
    await creer_lecture(session, site_id=site.site_id, timestamp=CIBLE, consumption_kwh=10.0)

    paires = await DriftRepository(session).paires(debut=DEBUT, fin=FIN, site_id=site.site_id)
    await session.rollback()

    assert [(p.predicted_value, p.actual_value) for p in paires] == [(12.0, 10.0)]


@pytest.mark.integration
async def test_repository_keeps_the_latest_run_when_several_predictions_share_a_target(
    session: AsyncSession,
) -> None:
    site = await creer_site(session)
    await creer_prediction(session, site_id=site.site_id, target_at=CIBLE, predicted_value=12.0)
    await creer_prediction(session, site_id=site.site_id, target_at=CIBLE, predicted_value=99.0)
    await creer_lecture(session, site_id=site.site_id, timestamp=CIBLE, consumption_kwh=10.0)

    paires = await DriftRepository(session).paires(debut=DEBUT, fin=FIN, site_id=site.site_id)
    await session.rollback()

    assert [p.predicted_value for p in paires] == [99.0]


@pytest.mark.integration
async def test_repository_keeps_one_reading_per_instant_when_two_sources_wrote_the_same_hour(
    session: AsyncSession,
) -> None:
    site = await creer_site(session)
    await creer_prediction(session, site_id=site.site_id, target_at=CIBLE, predicted_value=12.0)
    await creer_lecture(
        session, site_id=site.site_id, timestamp=CIBLE, source="api_current", consumption_kwh=10.0
    )
    await creer_lecture(
        session, site_id=site.site_id, timestamp=CIBLE, source="api_history", consumption_kwh=20.0
    )

    paires = await DriftRepository(session).paires(debut=DEBUT, fin=FIN, site_id=site.site_id)
    await session.rollback()

    assert [p.actual_value for p in paires] == [20.0]


@pytest.mark.integration
async def test_repository_excludes_an_insufficient_data_prediction_from_the_pairs(
    session: AsyncSession,
) -> None:
    site = await creer_site(session)
    await creer_prediction(
        session,
        site_id=site.site_id,
        target_at=CIBLE,
        predicted_value=None,
        status="insufficient_data",
        failure_reason="historique trop court",
    )
    await creer_lecture(session, site_id=site.site_id, timestamp=CIBLE, consumption_kwh=10.0)

    depot = DriftRepository(session)
    paires = await depot.paires(debut=DEBUT, fin=FIN, site_id=site.site_id)
    comptages = await depot.comptages(debut=DEBUT, fin=FIN, site_id=site.site_id)
    await session.rollback()

    assert paires == []
    assert [(c.status, c.nombre) for c in comptages] == [("insufficient_data", 1)]


@pytest.mark.integration
async def test_repository_excludes_a_target_outside_the_window(session: AsyncSession) -> None:
    site = await creer_site(session)
    hors_fenetre = FIN + timedelta(hours=1)
    await creer_prediction(
        session, site_id=site.site_id, target_at=hors_fenetre, predicted_value=12.0
    )
    await creer_lecture(session, site_id=site.site_id, timestamp=hors_fenetre, consumption_kwh=10.0)

    paires = await DriftRepository(session).paires(debut=DEBUT, fin=FIN, site_id=site.site_id)
    await session.rollback()

    assert paires == []


@pytest.mark.integration
async def test_repository_reads_back_the_global_report_it_wrote(session: AsyncSession) -> None:
    depot = DriftRepository(session)
    fenetre = datetime(2035, 3, 1, tzinfo=UTC)

    ecrites = await depot.enregistre([rapport(window_end=fenetre)])
    derniers = await depot.derniers()
    globaux = [r for r in derniers if r.site_id is None and r.window_end == fenetre]
    await session.rollback()

    assert ecrites == 1
    assert len(globaux) == 1


@pytest.mark.integration
async def test_repository_ignores_a_second_report_for_the_same_window_and_site(
    session: AsyncSession,
) -> None:
    depot = DriftRepository(session)
    fenetre = datetime(2035, 4, 1, tzinfo=UTC)

    premiere = await depot.enregistre([rapport(window_end=fenetre)])
    seconde = await depot.enregistre([rapport(window_end=fenetre, status="derive", reason="x")])
    await session.rollback()

    assert premiere == 1
    assert seconde == 0
