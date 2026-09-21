from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from app.models.energy import Site
from app.services.site import SiteNotFoundError, SiteService

TIMESTAMP = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


def site(site_id: str = "site-1") -> Site:
    return Site(
        site_id=site_id,
        site_name="Site de test",
        site_type="industriel",
        location="Toulouse",
        capacity_kw=42.0,
        status="actif",
    )


@dataclass
class FauxLecture:
    site_id: str
    timestamp: datetime = TIMESTAMP
    consumption_kw: float | None = 87.34
    consumption_kwh: float | None = 87.34
    voltage_v: float | None = 401.2
    current_a: float | None = 132.5
    power_factor: float | None = 0.923
    temperature_celsius: float | None = 22.1
    humidity_percent: float | None = 58.4
    null_reasons: list[str] | None = field(default_factory=list)
    data_quality: str | None = "good"


class FakeRepository:
    def __init__(self, sites: list[Site]) -> None:
        self._sites = sites

    async def list_all(self) -> list[Site]:
        return self._sites

    async def get_by_id(self, site_id: str) -> Site | None:
        return next((s for s in self._sites if s.site_id == site_id), None)


class FauxDepotLectures:
    def __init__(self, lectures: dict[str, FauxLecture]) -> None:
        self._lectures = lectures

    async def latest_for_site(self, site_id: str) -> FauxLecture | None:
        return self._lectures.get(site_id)


def service(sites: list[Site], lectures: dict[str, FauxLecture] | None = None) -> SiteService:
    return SiteService(
        sites=FakeRepository(sites),  # type: ignore[arg-type]
        readings=FauxDepotLectures(lectures or {}),  # type: ignore[arg-type]
    )


async def test_list_all_returns_the_repository_sites() -> None:
    svc = service([site("a"), site("b")])

    sites = await svc.list_all()

    assert [s.site_id for s in sites] == ["a", "b"]


async def test_get_by_id_returns_the_matching_site() -> None:
    svc = service([site("a")])

    trouve = await svc.get_by_id("a")

    assert trouve.site_id == "a"


async def test_get_by_id_raises_when_the_site_is_unknown() -> None:
    svc = service([])

    with pytest.raises(SiteNotFoundError):
        await svc.get_by_id("inconnu")


async def test_current_raises_when_the_site_is_unknown() -> None:
    svc = service([])

    with pytest.raises(SiteNotFoundError):
        await svc.current("inconnu")


async def test_current_returns_every_field_as_null_when_the_site_has_no_reading() -> None:
    svc = service([site("a")])

    actuel = await svc.current("a")

    assert actuel.timestamp is None
    assert actuel.consumption_kw is None
    assert actuel.data_quality == "critical"
    assert actuel.null_reasons == []


async def test_current_copies_every_field_from_the_latest_reading() -> None:
    svc = service([site("a")], {"a": FauxLecture(site_id="a")})

    actuel = await svc.current("a")

    assert actuel.timestamp == TIMESTAMP
    assert actuel.site_type == "industriel"
    assert actuel.consumption_kw == 87.34
    assert actuel.voltage_v == 401.2
    assert actuel.data_quality == "good"


async def test_current_treats_an_unknown_data_quality_as_critical() -> None:
    svc = service([site("a")], {"a": FauxLecture(site_id="a", data_quality=None)})

    actuel = await svc.current("a")

    assert actuel.data_quality == "critical"
