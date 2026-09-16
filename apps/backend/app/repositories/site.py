from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import Site


class SiteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> Sequence[Site]:
        requete = select(Site).order_by(Site.site_id)
        return (await self._session.scalars(requete)).all()

    async def get_by_id(self, site_id: str) -> Site | None:
        requete = select(Site).where(Site.site_id == site_id)
        site: Site | None = await self._session.scalar(requete)
        return site
