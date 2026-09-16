from collections.abc import Sequence

from app.models.energy import Site
from app.repositories.site import SiteRepository


class SiteError(Exception):
    pass


class SiteNotFoundError(SiteError):
    pass


class SiteService:
    def __init__(self, *, sites: SiteRepository) -> None:
        self._sites = sites

    async def list_all(self) -> Sequence[Site]:
        return await self._sites.list_all()

    async def get_by_id(self, site_id: str) -> Site:
        site = await self._sites.get_by_id(site_id)
        if site is None:
            raise SiteNotFoundError(site_id)
        return site
