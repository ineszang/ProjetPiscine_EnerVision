from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import Reading


class ReadingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def latest_by_site(self) -> Sequence[Reading]:
        # `.distinct(site_id)` compile en `DISTINCT ON (site_id)` sous PostgreSQL : une seule
        # ligne par site, la plus récente grâce à l'ordre composite qui suit.
        requete = (
            select(Reading)
            .distinct(Reading.site_id)
            .order_by(Reading.site_id, Reading.timestamp.desc())
        )
        return (await self._session.execute(requete)).scalars().all()

    async def latest_for_site(self, site_id: str) -> Reading | None:
        requete = (
            select(Reading)
            .where(Reading.site_id == site_id)
            .order_by(Reading.timestamp.desc())
            .limit(1)
        )
        return await self._session.scalar(requete)
