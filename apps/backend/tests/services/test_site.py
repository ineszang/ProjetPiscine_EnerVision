import pytest

from app.models.energy import Site
from app.services.site import SiteNotFoundError, SiteService


def site(site_id: str = "site-1") -> Site:
    return Site(
        site_id=site_id,
        site_name="Site de test",
        site_type="industriel",
        location="Toulouse",
        capacity_kw=42.0,
        status="actif",
    )


class FakeRepository:
    def __init__(self, sites: list[Site]) -> None:
        self._sites = sites

    async def list_all(self) -> list[Site]:
        return self._sites

    async def get_by_id(self, site_id: str) -> Site | None:
        return next((s for s in self._sites if s.site_id == site_id), None)


async def test_list_all_returns_the_repository_sites() -> None:
    service = SiteService(sites=FakeRepository([site("a"), site("b")]))

    sites = await service.list_all()

    assert [s.site_id for s in sites] == ["a", "b"]


async def test_get_by_id_returns_the_matching_site() -> None:
    service = SiteService(sites=FakeRepository([site("a")]))

    trouve = await service.get_by_id("a")

    assert trouve.site_id == "a"


async def test_get_by_id_raises_when_the_site_is_unknown() -> None:
    service = SiteService(sites=FakeRepository([]))

    with pytest.raises(SiteNotFoundError):
        await service.get_by_id("inconnu")
