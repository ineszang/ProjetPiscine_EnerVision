from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from app.models.energy import Reading, Site
from app.repositories.reading import ReadingRepository
from app.repositories.site import SiteRepository

DataQuality = Literal["good", "partial", "degraded", "critical"]

QUALITES_CONNUES: frozenset[str] = frozenset({"good", "partial", "degraded", "critical"})


@dataclass(frozen=True, slots=True)
class SiteConsumption:
    site_id: str
    site_name: str
    current_consumption_kw: float | None
    capacity_kw: float
    load_percent: float | None
    data_quality: DataQuality


@dataclass(frozen=True, slots=True)
class ConsumptionSummary:
    timestamp: datetime
    total_sites: int
    total_consumption_kw: float
    total_capacity_kw: float
    average_load_percent: float
    sites: list[SiteConsumption]


class StatsService:
    def __init__(self, sites: SiteRepository, readings: ReadingRepository) -> None:
        self._sites = sites
        self._readings = readings

    async def summary(self) -> ConsumptionSummary:
        sites = await self._sites.list_all()
        dernieres = {lecture.site_id: lecture for lecture in await self._readings.latest_by_site()}

        resumes = [self._resume_site(site, dernieres.get(site.site_id)) for site in sites]
        consommation_totale = sum(r.current_consumption_kw or 0 for r in resumes)
        capacite_totale = sum(r.capacity_kw for r in resumes)

        return ConsumptionSummary(
            timestamp=datetime.now(UTC),
            total_sites=len(resumes),
            total_consumption_kw=consommation_totale,
            total_capacity_kw=capacite_totale,
            average_load_percent=(
                consommation_totale / capacite_totale * 100 if capacite_totale > 0 else 0
            ),
            sites=resumes,
        )

    @staticmethod
    def _resume_site(site: Site, derniere: Reading | None) -> SiteConsumption:
        capacite = site.capacity_kw or 0
        # Piège : `data_quality` est nul dès qu'un site n'a jamais reçu de lecture, ou que le
        # producteur n'a pas su la qualifier. Le contrat frontend n'a pas de valeur pour ce cas,
        # `critical` est la seule des quatre qui n'induit pas une confiance qu'on n'a pas.
        qualite: DataQuality = "critical"
        consommation = None
        if derniere is not None and derniere.data_quality in QUALITES_CONNUES:
            qualite = derniere.data_quality  # type: ignore[assignment]
            consommation = derniere.consumption_kw

        charge = (
            consommation / capacite * 100 if consommation is not None and capacite > 0 else None
        )

        return SiteConsumption(
            site_id=site.site_id,
            site_name=site.site_name,
            current_consumption_kw=consommation,
            capacity_kw=capacite,
            load_percent=charge,
            data_quality=qualite,
        )
