from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.services.sensor import SensorService

TIMESTAMP = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


@dataclass
class FauxSite:
    site_id: str
    site_name: str


@dataclass
class FauxLecture:
    site_id: str
    timestamp: datetime
    data_quality: str | None
    null_reasons: list[str] | None = field(default_factory=list)
    consumption_kw: float | None = 10.0
    voltage_v: float | None = 230.0
    current_a: float | None = 5.0
    power_factor: float | None = 0.95
    temperature_celsius: float | None = 21.0
    humidity_percent: float | None = 40.0


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


async def test_status_marks_a_site_without_any_reading_as_critical_with_every_sensor_failing() -> (
    None
):
    service = SensorService(
        sites=FauxDepotSites([FauxSite("A", "Site A")]),  # type: ignore[arg-type]
        readings=FauxDepotLectures([]),  # type: ignore[arg-type]
    )

    etat = await service.status()

    site = etat.sites[0]
    assert site.overall == "critical"
    for capteur in (
        site.sensors.consumption,
        site.sensors.electrical,
        site.sensors.temperature,
        site.sensors.humidity,
        site.sensors.network,
    ):
        assert capteur.status == "failing"
        assert capteur.since is None


async def test_status_marks_every_sensor_ok_on_a_good_quality_reading_with_no_null_field() -> None:
    service = SensorService(
        sites=FauxDepotSites([FauxSite("A", "Site A")]),  # type: ignore[arg-type]
        readings=FauxDepotLectures([FauxLecture("A", TIMESTAMP, "good")]),  # type: ignore[arg-type]
    )

    etat = await service.status()

    site = etat.sites[0]
    assert site.overall == "ok"
    for capteur in (
        site.sensors.consumption,
        site.sensors.electrical,
        site.sensors.temperature,
        site.sensors.humidity,
        site.sensors.network,
    ):
        assert capteur.status == "ok"
        assert capteur.since is None


async def test_status_flags_the_sensor_named_in_null_reasons() -> None:
    service = SensorService(
        sites=FauxDepotSites([FauxSite("A", "Site A")]),  # type: ignore[arg-type]
        readings=FauxDepotLectures(  # type: ignore[arg-type]
            [
                FauxLecture(
                    "A",
                    TIMESTAMP,
                    "partial",
                    null_reasons=["temperature_sensor_failure"],
                    temperature_celsius=None,
                )
            ]
        ),
    )

    etat = await service.status()

    site = etat.sites[0]
    assert site.overall == "degraded"
    assert site.sensors.temperature.status == "failing"
    assert site.sensors.temperature.since == TIMESTAMP
    assert site.sensors.consumption.status == "ok"
    assert site.sensors.electrical.status == "ok"
    assert site.sensors.humidity.status == "ok"
    assert site.sensors.network.status == "ok"


async def test_status_flags_a_sensor_from_a_null_field_even_without_a_null_reason() -> None:
    service = SensorService(
        sites=FauxDepotSites([FauxSite("A", "Site A")]),  # type: ignore[arg-type]
        readings=FauxDepotLectures(  # type: ignore[arg-type]
            [FauxLecture("A", TIMESTAMP, "partial", null_reasons=[], humidity_percent=None)]
        ),
    )

    etat = await service.status()

    site = etat.sites[0]
    assert site.sensors.humidity.status == "failing"
    assert site.sensors.humidity.since == TIMESTAMP


async def test_status_flags_electrical_as_failing_when_any_of_its_three_fields_is_null() -> None:
    service = SensorService(
        sites=FauxDepotSites([FauxSite("A", "Site A")]),  # type: ignore[arg-type]
        readings=FauxDepotLectures(  # type: ignore[arg-type]
            [FauxLecture("A", TIMESTAMP, "partial", null_reasons=[], power_factor=None)]
        ),
    )

    etat = await service.status()

    site = etat.sites[0]
    assert site.sensors.electrical.status == "failing"


async def test_status_forces_every_sensor_to_failing_when_overall_is_critical() -> None:
    service = SensorService(
        sites=FauxDepotSites([FauxSite("A", "Site A")]),  # type: ignore[arg-type]
        readings=FauxDepotLectures([FauxLecture("A", TIMESTAMP, "critical", null_reasons=[])]),  # type: ignore[arg-type]
    )

    etat = await service.status()

    site = etat.sites[0]
    assert site.overall == "critical"
    for capteur in (
        site.sensors.consumption,
        site.sensors.electrical,
        site.sensors.temperature,
        site.sensors.humidity,
        site.sensors.network,
    ):
        assert capteur.status == "failing"
        assert capteur.since == TIMESTAMP


async def test_status_treats_an_unknown_data_quality_as_critical() -> None:
    service = SensorService(
        sites=FauxDepotSites([FauxSite("A", "Site A")]),  # type: ignore[arg-type]
        readings=FauxDepotLectures([FauxLecture("A", TIMESTAMP, None, null_reasons=[])]),  # type: ignore[arg-type]
    )

    etat = await service.status()

    assert etat.sites[0].overall == "critical"


async def test_status_ignores_an_unknown_null_reason() -> None:
    service = SensorService(
        sites=FauxDepotSites([FauxSite("A", "Site A")]),  # type: ignore[arg-type]
        readings=FauxDepotLectures(  # type: ignore[arg-type]
            [FauxLecture("A", TIMESTAMP, "good", null_reasons=["something_else"])]
        ),
    )

    etat = await service.status()

    site = etat.sites[0]
    assert site.overall == "ok"
    for capteur in (
        site.sensors.consumption,
        site.sensors.electrical,
        site.sensors.temperature,
        site.sensors.humidity,
        site.sensors.network,
    ):
        assert capteur.status == "ok"


async def test_status_flags_network_from_null_reasons_only() -> None:
    service = SensorService(
        sites=FauxDepotSites([FauxSite("A", "Site A")]),  # type: ignore[arg-type]
        readings=FauxDepotLectures(  # type: ignore[arg-type]
            [
                FauxLecture(
                    "A",
                    TIMESTAMP,
                    "partial",
                    null_reasons=["network_loss"],
                )
            ]
        ),
    )

    etat = await service.status()

    site = etat.sites[0]
    assert site.overall == "degraded"
    assert site.sensors.network.status == "failing"
    assert site.sensors.network.since == TIMESTAMP
    assert site.sensors.consumption.status == "ok"
    assert site.sensors.electrical.status == "ok"
    assert site.sensors.temperature.status == "ok"
    assert site.sensors.humidity.status == "ok"
