from dataclasses import dataclass
from datetime import UTC, datetime

from app.models.energy import Prediction, Site
from app.repositories.prediction import PredictionRepository
from app.repositories.site import SiteRepository


@dataclass(frozen=True, slots=True)
class SitePrediction:
    target_at: datetime
    target_metric: str
    period_minutes: int | None
    predicted_value: float | None
    status: str
    failure_reason: str | None
    model_reference: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SitePredictionSummary:
    site_id: str
    site_name: str
    prediction: SitePrediction | None


@dataclass(frozen=True, slots=True)
class PredictionSummary:
    timestamp: datetime
    sites: list[SitePredictionSummary]


class PredictionService:
    def __init__(self, sites: SiteRepository, predictions: PredictionRepository) -> None:
        self._sites = sites
        self._predictions = predictions

    async def summary(self) -> PredictionSummary:
        sites = await self._sites.list_all()
        dernieres = {p.site_id: p for p in await self._predictions.latest_by_site()}

        return PredictionSummary(
            timestamp=datetime.now(UTC),
            sites=[_resume_site(site, dernieres.get(site.site_id)) for site in sites],
        )


def _resume_site(site: Site, derniere: Prediction | None) -> SitePredictionSummary:
    # Piège : l'absence de ligne signifie « jamais scoré », pas une valeur pseudo-statut, qui
    # n'existe pas dans la contrainte de la table. `prediction` reste `None` plutôt que de
    # fabriquer un statut absent du domaine `available`/`insufficient_data`/`error`.
    prediction = None
    if derniere is not None:
        prediction = SitePrediction(
            target_at=derniere.target_at,
            target_metric=derniere.target_metric,
            period_minutes=derniere.period_minutes,
            predicted_value=derniere.predicted_value,
            status=derniere.status,
            failure_reason=derniere.failure_reason,
            model_reference=derniere.model_reference,
            created_at=derniere.created_at,
        )

    return SitePredictionSummary(
        site_id=site.site_id, site_name=site.site_name, prediction=prediction
    )
