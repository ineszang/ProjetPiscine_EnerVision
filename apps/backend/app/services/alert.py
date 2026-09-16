from collections.abc import Sequence

from app.models.energy import Alert
from app.repositories.alert import AlertRepository


class AlertService:
    def __init__(self, *, alerts: AlertRepository) -> None:
        self._alerts = alerts

    async def list_all(
        self, *, site_id: str | None = None, severity: str | None = None
    ) -> Sequence[Alert]:
        return await self._alerts.list_all(site_id=site_id, severity=severity)
