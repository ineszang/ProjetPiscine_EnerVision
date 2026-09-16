import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import Alert
from app.repositories.alert import AlertRepository
from tests.repositories.test_site import creer as creer_site
from tests.repositories.test_site import identifiant as identifiant_site

pytestmark = pytest.mark.integration


async def creer_alerte(session: AsyncSession, *, site_id: str, **overrides: object) -> Alert:
    alerte = Alert(
        source_alert_id=overrides.get("source_alert_id", f"ALR-{uuid.uuid4().hex[:12]}"),
        site_id=site_id,
        source=overrides.get("source", "enervision"),
        timestamp=overrides.get("timestamp", datetime(2026, 9, 16, tzinfo=UTC)),
        type=overrides.get("type", "threshold"),
        severity=overrides.get("severity", "high"),
        message=overrides.get("message", "Dépassement du seuil configuré"),
        value=overrides.get("value", 812.5),
        threshold=overrides.get("threshold", 720.0),
        metric=overrides.get("metric", "consumption_kw"),
        prediction_id=overrides.get("prediction_id"),
        raw_data=overrides.get("raw_data", {}),
    )
    session.add(alerte)
    await session.flush()
    return alerte


async def test_list_all_returns_the_alerts_sorted_by_timestamp_descending(
    session: AsyncSession,
) -> None:
    site = await creer_site(session)
    depot = AlertRepository(session)
    ancienne = await creer_alerte(
        session, site_id=site.site_id, timestamp=datetime(2026, 9, 1, tzinfo=UTC)
    )
    recente = await creer_alerte(
        session, site_id=site.site_id, timestamp=datetime(2026, 9, 15, tzinfo=UTC)
    )

    alertes = await depot.list_all()
    identifiants = [
        a.alert_id for a in alertes if a.alert_id in (ancienne.alert_id, recente.alert_id)
    ]
    await session.rollback()

    assert identifiants == [recente.alert_id, ancienne.alert_id]


async def test_list_all_filters_by_site_id(session: AsyncSession) -> None:
    premier = await creer_site(session)
    second = await creer_site(session)
    depot = AlertRepository(session)
    voulue = await creer_alerte(session, site_id=premier.site_id)
    await creer_alerte(session, site_id=second.site_id)

    alertes = await depot.list_all(site_id=premier.site_id)
    identifiants = [a.alert_id for a in alertes]
    await session.rollback()

    assert identifiants == [voulue.alert_id]


async def test_list_all_filters_by_severity(session: AsyncSession) -> None:
    site = await creer_site(session)
    depot = AlertRepository(session)
    voulue = await creer_alerte(session, site_id=site.site_id, severity="critical")
    await creer_alerte(session, site_id=site.site_id, severity="low")

    alertes = await depot.list_all(severity="critical")
    identifiants = [a.alert_id for a in alertes]
    await session.rollback()

    assert identifiants == [voulue.alert_id]


async def test_list_all_returns_an_empty_list_when_there_is_nothing(
    session: AsyncSession,
) -> None:
    depot = AlertRepository(session)

    alertes = await depot.list_all(site_id=identifiant_site())

    assert list(alertes) == []
