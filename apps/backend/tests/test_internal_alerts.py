from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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
    site = await creer_site(session, capacity_kw=100.0)
    instant = datetime(2026, 9, 16, 12, tzinfo=UTC)
    await creer_lecture(session, site_id=site.site_id, timestamp=instant, consumption_kw=150.0)
    await session.commit()

    nombre = await internal_alerts.run_detection(now=instant, site_id=site.site_id)

    alertes = await AlertRepository(session).list_all(site_id=site.site_id)
    types = [a.type for a in alertes]
    await session.rollback()

    assert nombre == 1
    assert types == ["threshold"]
