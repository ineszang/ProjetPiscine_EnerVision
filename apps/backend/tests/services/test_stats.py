from dataclasses import dataclass

from app.services.stats import StatsService


@dataclass
class FauxSite:
    site_id: str
    site_name: str
    capacity_kw: float | None


@dataclass
class FauxLecture:
    site_id: str
    consumption_kw: float | None
    data_quality: str | None


class FauxDepotSites:
    def __init__(self, sites: list[FauxSite]) -> None:
        self._sites = sites

    async def list_all(self) -> list[FauxSite]:
        return self._sites


class FauxDepotLectures:
    def __init__(self, lectures: list[FauxLecture]) -> None:
        self._lectures = lectures

    async def latest_by_site(self) -> list[FauxLecture]:
        return self._lectures


async def test_summary_computes_totals_and_the_average_load() -> None:
    service = StatsService(
        sites=FauxDepotSites([FauxSite("A", "Site A", 200), FauxSite("B", "Site B", 800)]),  # type: ignore[arg-type]
        readings=FauxDepotLectures(  # type: ignore[arg-type]
            [
                FauxLecture("A", 100, "good"),
                FauxLecture("B", 400, "good"),
            ]
        ),
    )

    resume = await service.summary()

    assert resume.total_sites == 2
    assert resume.total_consumption_kw == 500
    assert resume.total_capacity_kw == 1000
    assert resume.average_load_percent == 50
    par_site = {site.site_id: site for site in resume.sites}
    assert par_site["A"].load_percent == 50
    assert par_site["B"].load_percent == 50


async def test_summary_treats_a_site_without_any_reading_as_critical() -> None:
    service = StatsService(
        sites=FauxDepotSites([FauxSite("A", "Site A", 200)]),  # type: ignore[arg-type]
        readings=FauxDepotLectures([]),  # type: ignore[arg-type]
    )

    resume = await service.summary()

    site = resume.sites[0]
    assert site.data_quality == "critical"
    assert site.current_consumption_kw is None
    assert site.load_percent is None


async def test_summary_treats_a_reading_with_an_unknown_quality_as_critical() -> None:
    service = StatsService(
        sites=FauxDepotSites([FauxSite("A", "Site A", 200)]),  # type: ignore[arg-type]
        readings=FauxDepotLectures([FauxLecture("A", 50, None)]),  # type: ignore[arg-type]
    )

    resume = await service.summary()

    site = resume.sites[0]
    assert site.data_quality == "critical"
    assert site.current_consumption_kw is None


async def test_summary_exposes_a_missing_capacity_as_zero_without_dividing_by_it() -> None:
    service = StatsService(
        sites=FauxDepotSites([FauxSite("A", "Site A", None)]),  # type: ignore[arg-type]
        readings=FauxDepotLectures([FauxLecture("A", 50, "good")]),  # type: ignore[arg-type]
    )

    resume = await service.summary()

    site = resume.sites[0]
    assert site.capacity_kw == 0
    assert site.current_consumption_kw == 50
    assert site.load_percent is None


async def test_summary_returns_zero_average_load_when_no_site_has_a_capacity() -> None:
    service = StatsService(
        sites=FauxDepotSites([FauxSite("A", "Site A", None)]),  # type: ignore[arg-type]
        readings=FauxDepotLectures([]),  # type: ignore[arg-type]
    )

    resume = await service.summary()

    assert resume.average_load_percent == 0
