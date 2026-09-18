from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import Prediction
from app.repositories.prediction import PredictionRepository
from tests.repositories.test_site import creer as creer_site
from tests.repositories.test_site import identifiant as identifiant_site

pytestmark = pytest.mark.integration


async def creer_prediction(
    session: AsyncSession, *, site_id: str, **overrides: object
) -> Prediction:
    prediction = Prediction(
        site_id=site_id,
        target_at=overrides.get("target_at", datetime(2026, 9, 16, tzinfo=UTC)),
        target_metric=overrides.get("target_metric", "consumption_kwh"),
        period_minutes=overrides.get("period_minutes", 60),
        predicted_value=overrides.get("predicted_value", 42.0),
        model_reference=overrides.get("model_reference", "lightgbm-test"),
        status=overrides.get("status", "available"),
        failure_reason=overrides.get("failure_reason"),
    )
    session.add(prediction)
    await session.flush()
    return prediction


async def test_list_since_excludes_predictions_before_the_cutoff(session: AsyncSession) -> None:
    site = await creer_site(session)
    depot = PredictionRepository(session)
    dedans = await creer_prediction(
        session, site_id=site.site_id, target_at=datetime(2026, 9, 16, tzinfo=UTC)
    )
    await creer_prediction(
        session, site_id=site.site_id, target_at=datetime(2026, 9, 1, tzinfo=UTC)
    )

    resultats = await depot.list_since(
        since=datetime(2026, 9, 10, tzinfo=UTC), site_id=site.site_id
    )
    identifiants = [p.prediction_id for p in resultats]
    await session.rollback()

    assert identifiants == [dedans.prediction_id]


async def test_list_since_excludes_predictions_that_are_not_available(
    session: AsyncSession,
) -> None:
    site = await creer_site(session)
    depot = PredictionRepository(session)
    await creer_prediction(
        session,
        site_id=site.site_id,
        target_at=datetime(2026, 9, 16, tzinfo=UTC),
        status="insufficient_data",
        predicted_value=None,
        failure_reason="pas assez d'historique",
    )

    resultats = await depot.list_since(since=datetime(2026, 9, 1, tzinfo=UTC), site_id=site.site_id)
    await session.rollback()

    assert list(resultats) == []


async def test_list_since_filters_by_site_id(session: AsyncSession) -> None:
    premier = await creer_site(session)
    second = await creer_site(session)
    depot = PredictionRepository(session)
    voulue = await creer_prediction(session, site_id=premier.site_id)
    await creer_prediction(session, site_id=second.site_id)

    resultats = await depot.list_since(
        since=datetime(2026, 8, 1, tzinfo=UTC), site_id=premier.site_id
    )
    identifiants = [p.prediction_id for p in resultats]
    await session.rollback()

    assert identifiants == [voulue.prediction_id]


async def test_latest_by_site_keeps_only_the_most_recent_target(session: AsyncSession) -> None:
    site = await creer_site(session)
    depot = PredictionRepository(session)
    ancienne = await creer_prediction(
        session, site_id=site.site_id, target_at=datetime(2026, 9, 1, tzinfo=UTC)
    )
    recente = await creer_prediction(
        session, site_id=site.site_id, target_at=datetime(2026, 9, 15, tzinfo=UTC)
    )

    resultats = await depot.latest_by_site()
    identifiants = [
        p.prediction_id
        for p in resultats
        if p.prediction_id in (ancienne.prediction_id, recente.prediction_id)
    ]
    await session.rollback()

    assert identifiants == [recente.prediction_id]


async def test_latest_by_site_returns_one_row_per_site(session: AsyncSession) -> None:
    premier = await creer_site(session)
    second = await creer_site(session)
    depot = PredictionRepository(session)
    voulue_premier = await creer_prediction(session, site_id=premier.site_id)
    voulue_second = await creer_prediction(session, site_id=second.site_id)

    resultats = await depot.latest_by_site()
    identifiants = {p.site_id for p in resultats if p.site_id in (premier.site_id, second.site_id)}
    await session.rollback()

    assert identifiants == {voulue_premier.site_id, voulue_second.site_id}


async def test_latest_by_site_keeps_an_insufficient_data_prediction(session: AsyncSession) -> None:
    site = await creer_site(session)
    depot = PredictionRepository(session)
    voulue = await creer_prediction(
        session,
        site_id=site.site_id,
        status="insufficient_data",
        predicted_value=None,
        failure_reason="pas assez d'historique",
    )

    resultats = await depot.latest_by_site()
    identifiants = [p.prediction_id for p in resultats if p.site_id == site.site_id]
    await session.rollback()

    assert identifiants == [voulue.prediction_id]


async def test_latest_by_site_returns_an_empty_list_when_there_is_nothing(
    session: AsyncSession,
) -> None:
    depot = PredictionRepository(session)

    resultats = [p for p in await depot.latest_by_site() if p.site_id == identifiant_site()]

    assert resultats == []
