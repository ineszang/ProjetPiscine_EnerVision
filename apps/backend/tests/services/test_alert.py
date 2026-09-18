from datetime import UTC, datetime

from app.models.energy import Alert
from app.services.alert import AlertService


def alert(
    alert_id: int = 1,
    site_id: str = "site-1",
    severity: str = "high",
) -> Alert:
    return Alert(
        alert_id=alert_id,
        source_alert_id=f"ALR-{alert_id}",
        site_id=site_id,
        source="enervision",
        timestamp=datetime(2026, 9, 16, tzinfo=UTC),
        type="threshold",
        severity=severity,
        message="Dépassement du seuil configuré",
        value=812.5,
        threshold=720.0,
        metric="consumption_kw",
        prediction_id=None,
        raw_data={},
    )


class FakeRepository:
    def __init__(self, alerts: list[Alert]) -> None:
        self._alerts = alerts
        self.appels: list[tuple[str | None, str | None]] = []

    async def list_all(
        self, *, site_id: str | None = None, severity: str | None = None
    ) -> list[Alert]:
        self.appels.append((site_id, severity))
        return self._alerts


async def test_list_all_returns_the_repository_alerts() -> None:
    service = AlertService(alerts=FakeRepository([alert(1), alert(2)]))

    alertes = await service.list_all()

    assert [a.alert_id for a in alertes] == [1, 2]


async def test_list_all_relays_the_filters_to_the_repository() -> None:
    depot = FakeRepository([])
    service = AlertService(alerts=depot)

    await service.list_all(site_id="site-1", severity="critical")

    assert depot.appels == [("site-1", "critical")]
