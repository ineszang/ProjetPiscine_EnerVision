from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.models.energy import Site
from app.repositories.reading import ReadingRepository
from app.repositories.site import SiteRepository

DataQuality = Literal["good", "partial", "degraded", "critical"]

QUALITES_CONNUES: frozenset[str] = frozenset({"good", "partial", "degraded", "critical"})


class SiteError(Exception):
    pass


class SiteNotFoundError(SiteError):
    pass


@dataclass(frozen=True, slots=True)
class SiteCurrentReading:
    timestamp: datetime | None
    site_id: str
    site_type: str
    consumption_kw: float | None
    consumption_kwh: float | None
    voltage_v: float | None
    current_a: float | None
    power_factor: float | None
    temperature_celsius: float | None
    humidity_percent: float | None
    null_reasons: list[str]
    data_quality: DataQuality


class SiteService:
    def __init__(self, *, sites: SiteRepository, readings: ReadingRepository) -> None:
        self._sites = sites
        self._readings = readings

    async def list_all(self) -> Sequence[Site]:
        return await self._sites.list_all()

    async def get_by_id(self, site_id: str) -> Site:
        site = await self._sites.get_by_id(site_id)
        if site is None:
            raise SiteNotFoundError(site_id)
        return site

    async def current(self, site_id: str) -> SiteCurrentReading:
        site = await self.get_by_id(site_id)
        derniere = await self._readings.latest_for_site(site_id)

        if derniere is None:
            return SiteCurrentReading(
                timestamp=None,
                site_id=site.site_id,
                site_type=site.site_type,
                consumption_kw=None,
                consumption_kwh=None,
                voltage_v=None,
                current_a=None,
                power_factor=None,
                temperature_celsius=None,
                humidity_percent=None,
                null_reasons=[],
                data_quality="critical",
            )

        qualite: DataQuality = (
            derniere.data_quality if derniere.data_quality in QUALITES_CONNUES else "critical"
        )
        return SiteCurrentReading(
            timestamp=derniere.timestamp,
            site_id=site.site_id,
            site_type=site.site_type,
            consumption_kw=derniere.consumption_kw,
            consumption_kwh=derniere.consumption_kwh,
            voltage_v=derniere.voltage_v,
            current_a=derniere.current_a,
            power_factor=derniere.power_factor,
            temperature_celsius=derniere.temperature_celsius,
            humidity_percent=derniere.humidity_percent,
            null_reasons=derniere.null_reasons or [],
            data_quality=qualite,
        )
