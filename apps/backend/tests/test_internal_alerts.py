from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session_factory
from app.detection import internal_alerts
from app.repositories.alert import AlertRepository
from tests.repositories.test_reading import creer_lecture
from tests.repositories.test_site import creer as creer_site


def test_parse_args_defaults_to_no_site_and_no_instant() -> None:
    arguments = internal_alerts.parse_args([])

    assert arguments.site_id is None
    assert arguments.now is None


def test_parse_args_reads_the_site_id() -> None:
    arguments = internal_alerts.parse_args(["--site-id", "site-1"])

    assert arguments.site_id == "site-1"


def test_parse_args_parses_the_instant_option() -> None:
    arguments = internal_alerts.parse_args(["--now", "2026-09-16T12:00:00+00:00"])

    assert arguments.now == datetime(2026, 9, 16, 12, tzinfo=UTC)


def test_parse_instant_treats_a_naive_datetime_as_utc() -> None:
    assert internal_alerts._parse_instant("2026-09-16T12:00:00") == datetime(
        2026, 9, 16, 12, tzinfo=UTC
    )


def test_main_prints_how_many_alerts_were_recorded(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fausse_execution(*, now: datetime | None, site_id: str | None) -> int:
        return 3

    monkeypatch.setattr(internal_alerts, "run_detection", fausse_execution)

    code = internal_alerts.main([])

    assert code == 0
    assert "3 nouvelle" in capsys.readouterr().out


@pytest.mark.integration
async def test_run_detection_writes_a_threshold_alert_end_to_end(session: AsyncSession) -> None:
    # `run_detection` ouvre sa propre session et commite : `session.rollback()` seul ne défait
    # rien ici (contrairement au reste de la suite), d'où le nettoyage explicite ci-dessous, sur
    # le modèle de `tests/api/test_matrice_acces.py`.
    site = await creer_site(session, capacity_kw=100.0)
    site_id = site.site_id
    instant = datetime(2026, 9, 16, 12, tzinfo=UTC)
    await creer_lecture(session, site_id=site_id, timestamp=instant, consumption_kw=150.0)
    await session.commit()

    try:
        nombre = await internal_alerts.run_detection(now=instant, site_id=site_id)

        alertes = await AlertRepository(session).list_all(site_id=site_id)
        types = [a.type for a in alertes]
        await session.rollback()

        assert nombre == 1
        assert types == ["threshold"]
    finally:
        # `site.site_id` n'est plus sûr après `session.rollback()` : le rollback expire tous les
        # objets de la session (indépendamment d'`expire_on_commit`), et y accéder ici relance une
        # requête hors contexte async. D'où `site_id`, capturé avant.
        async with get_session_factory()() as nettoyage:
            await nettoyage.execute(
                text("delete from alert where site_id = :site_id"), {"site_id": site_id}
            )
            await nettoyage.execute(
                text("delete from reading where site_id = :site_id"), {"site_id": site_id}
            )
            await nettoyage.execute(
                text("delete from site where site_id = :site_id"), {"site_id": site_id}
            )
            await nettoyage.commit()
