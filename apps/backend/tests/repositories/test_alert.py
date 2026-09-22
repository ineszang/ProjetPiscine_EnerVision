import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import Alert
from app.repositories import alert as module_alert
from app.repositories.alert import AlertRepository
from app.schemas.alert import AlertSeverity
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

    alertes = await depot.list_all(severity=AlertSeverity.CRITICAL)
    identifiants = [a.alert_id for a in alertes]
    await session.rollback()

    assert identifiants == [voulue.alert_id]


async def test_list_all_returns_an_empty_list_when_there_is_nothing(
    session: AsyncSession,
) -> None:
    depot = AlertRepository(session)

    alertes = await depot.list_all(site_id=identifiant_site())

    assert list(alertes) == []


def _alerte_a_inserer(*, site_id: str, source_alert_id: str) -> Alert:
    return Alert(
        source_alert_id=source_alert_id,
        site_id=site_id,
        source="enervision",
        timestamp=datetime(2026, 9, 16, tzinfo=UTC),
        type="threshold",
        severity="high",
        message="Dépassement du seuil configuré",
        value=812.5,
        threshold=720.0,
        metric="consumption_kw",
        prediction_id=None,
        raw_data={},
    )


async def test_create_many_inserts_every_alert(session: AsyncSession) -> None:
    site = await creer_site(session)
    depot = AlertRepository(session)

    creees = await depot.create_many(
        [
            _alerte_a_inserer(site_id=site.site_id, source_alert_id="threshold:a"),
            _alerte_a_inserer(site_id=site.site_id, source_alert_id="threshold:b"),
        ]
    )
    identifiants = [a.alert_id for a in creees]
    await session.rollback()

    assert len(identifiants) == 2
    assert all(identifiant is not None for identifiant in identifiants)


async def test_create_many_skips_a_duplicate_source_alert_id(session: AsyncSession) -> None:
    site = await creer_site(session)
    depot = AlertRepository(session)
    await depot.create_many(
        [_alerte_a_inserer(site_id=site.site_id, source_alert_id="threshold:rejouee")]
    )

    rejouees = await depot.create_many(
        [_alerte_a_inserer(site_id=site.site_id, source_alert_id="threshold:rejouee")]
    )
    await session.rollback()

    assert rejouees == []


async def test_create_many_does_nothing_for_an_empty_list(session: AsyncSession) -> None:
    depot = AlertRepository(session)

    creees = await depot.create_many([])

    assert creees == []


async def test_create_many_inserts_every_alert_across_several_batches(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module_alert, "TAILLE_DE_LOT", 2)
    site = await creer_site(session)
    depot = AlertRepository(session)
    a_inserer = [
        _alerte_a_inserer(site_id=site.site_id, source_alert_id=f"threshold:lot-{index}")
        for index in range(5)
    ]

    creees = await depot.create_many(a_inserer)
    await session.rollback()

    assert len(creees) == 5
