from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.models.energy import Recommendation
from app.repositories.alert import AlertRepository
from app.repositories.recommendation import RecommendationRepository
from app.services.recommendation_rules import applique_les_regles


class Transaction(Protocol):
    async def commit(self) -> None: ...


class RecommendationError(Exception):
    pass


class RecommendationNotFoundError(RecommendationError):
    pass


@dataclass(frozen=True, slots=True)
class RapportGeneration:
    alertes_examinees: int
    recommandations_creees: int
    deja_presentes: int


class RecommendationService:
    def __init__(
        self,
        *,
        recommendations: RecommendationRepository,
        alerts: AlertRepository,
        transaction: Transaction,
    ) -> None:
        self._recommendations = recommendations
        self._alerts = alerts
        self._transaction = transaction

    async def list_all(self) -> Sequence[Recommendation]:
        return await self._recommendations.list_all()

    async def get_by_id(self, recommendation_id: int) -> Recommendation:
        recommendation = await self._recommendations.get_by_id(recommendation_id)
        if recommendation is None:
            raise RecommendationNotFoundError(recommendation_id)
        return recommendation

    async def generate(self, *, site_id: str | None = None) -> RapportGeneration:
        alertes = await self._alerts.list_all(site_id=site_id)
        nouvelles = [nouvelle for alerte in alertes for nouvelle in applique_les_regles(alerte)]

        creees = await self._recommendations.create_missing(nouvelles)
        await self._transaction.commit()

        return RapportGeneration(
            alertes_examinees=len(alertes),
            recommandations_creees=creees,
            deja_presentes=len(nouvelles) - creees,
        )
