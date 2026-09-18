import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import Alert, Recommendation, Site
from app.repositories.recommendation import NouvelleRecommandation, RecommendationRepository

pytestmark = pytest.mark.integration

MOMENT = datetime(2024, 1, 1, tzinfo=UTC)


async def creer_site(session: AsyncSession) -> str:
    site_id = f"TEST-{uuid.uuid4()}"
    session.add(Site(site_id=site_id, site_name="Site de test", site_type="office"))
    await session.flush()
    return site_id


async def creer_alerte(session: AsyncSession) -> int:
    site_id = await creer_site(session)
    alerte = Alert(
        source_alert_id=str(uuid.uuid4()),
        site_id=site_id,
        source="api_mock",
        timestamp=MOMENT,
        type="spike",
        severity="high",
        message="Test",
        raw_data={},
    )
    session.add(alerte)
    await session.flush()
    return alerte.alert_id


async def creer(session: AsyncSession, **overrides: object) -> Recommendation:
    recommendation = Recommendation(
        alert_id=overrides.get("alert_id") or await creer_alerte(session),
        action=overrides.get("action", "Vérifier la consommation"),
        explanation=overrides.get("explanation", "Pic détecté"),
        rule_reference=overrides.get("rule_reference", f"spike-{uuid.uuid4().hex[:8]}"),
    )
    session.add(recommendation)
    await session.flush()
    return recommendation


async def test_get_by_id_returns_the_matching_recommendation(session: AsyncSession) -> None:
    depot = RecommendationRepository(session)
    cree = await creer(session)

    trouve = await depot.get_by_id(cree.recommendation_id)
    action = trouve.action if trouve else None
    await session.rollback()

    assert action == "Vérifier la consommation"


async def test_get_by_id_returns_nothing_for_an_unknown_identifier(
    session: AsyncSession,
) -> None:
    trouve = await RecommendationRepository(session).get_by_id(0)

    assert trouve is None


async def test_list_all_returns_the_recommendations_sorted_by_identifier(
    session: AsyncSession,
) -> None:
    depot = RecommendationRepository(session)
    premiere = await creer(session)
    seconde = await creer(session)

    recommendations = await depot.list_all()
    identifiants = [
        r.recommendation_id
        for r in recommendations
        if r.recommendation_id in (premiere.recommendation_id, seconde.recommendation_id)
    ]
    await session.rollback()

    assert identifiants == sorted(identifiants)


def nouvelle(alert_id: int, reference: str = "spike-delestage-v1") -> NouvelleRecommandation:
    return NouvelleRecommandation(
        alert_id=alert_id,
        action="Délester les équipements non prioritaires",
        explanation="Pic de consommation signalé.",
        rule_reference=reference,
    )


async def test_create_missing_inserts_the_proposals(session: AsyncSession) -> None:
    depot = RecommendationRepository(session)
    alert_id = await creer_alerte(session)

    creees = await depot.create_missing(
        [nouvelle(alert_id), nouvelle(alert_id, "escalade-astreinte-v1")]
    )
    await session.rollback()

    assert creees == 2


async def test_create_missing_ignores_a_rule_already_held_for_the_alert(
    session: AsyncSession,
) -> None:
    depot = RecommendationRepository(session)
    alert_id = await creer_alerte(session)
    await depot.create_missing([nouvelle(alert_id)])

    creees = await depot.create_missing([nouvelle(alert_id)])
    await session.rollback()

    assert creees == 0


async def test_create_missing_returns_zero_without_any_proposal(session: AsyncSession) -> None:
    creees = await RecommendationRepository(session).create_missing([])

    assert creees == 0
