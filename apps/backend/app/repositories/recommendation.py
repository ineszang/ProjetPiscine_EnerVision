from collections.abc import Sequence
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import Recommendation


@dataclass(frozen=True, slots=True)
class NouvelleRecommandation:
    alert_id: int
    action: str
    explanation: str
    rule_reference: str


class RecommendationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> Sequence[Recommendation]:
        requete = select(Recommendation).order_by(Recommendation.recommendation_id)
        return (await self._session.scalars(requete)).all()

    async def get_by_id(self, recommendation_id: int) -> Recommendation | None:
        requete = select(Recommendation).where(
            Recommendation.recommendation_id == recommendation_id
        )
        recommendation: Recommendation | None = await self._session.scalar(requete)
        return recommendation

    # Pourquoi : l'idempotence est déléguée à `uq_recommendation_alert_rule` plutôt qu'à une
    # lecture préalable, qui laisserait une fenêtre entre le contrôle et l'insertion.
    async def create_missing(self, nouvelles: Sequence[NouvelleRecommandation]) -> int:
        if not nouvelles:
            return 0

        requete = (
            insert(Recommendation)
            .values([asdict(nouvelle) for nouvelle in nouvelles])
            .on_conflict_do_nothing(constraint="uq_recommendation_alert_rule")
            .returning(Recommendation.recommendation_id)
        )
        creees = (await self._session.scalars(requete)).all()
        return len(creees)
