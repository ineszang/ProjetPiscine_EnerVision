from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import Alert


class AlertRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(
        self, *, site_id: str | None = None, severity: str | None = None
    ) -> Sequence[Alert]:
        requete = select(Alert).order_by(Alert.timestamp.desc(), Alert.alert_id.desc())
        if site_id is not None:
            requete = requete.where(Alert.site_id == site_id)
        if severity is not None:
            requete = requete.where(Alert.severity == severity)
        return (await self._session.scalars(requete)).all()
