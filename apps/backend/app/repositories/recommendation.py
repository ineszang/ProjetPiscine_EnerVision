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


TAILLE_DE_LOT = 1000


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
        creees = 0
        # Piège : asyncpg plafonne une requête à 32 767 paramètres, soit 8 191 lignes de quatre
        # colonnes. Au-delà de ce seuil un `INSERT` d'un seul tenant échouerait.
        for debut in range(0, len(nouvelles), TAILLE_DE_LOT):
            requete = (
                insert(Recommendation)
                .values([asdict(nouvelle) for nouvelle in nouvelles[debut : debut + TAILLE_DE_LOT]])
                .on_conflict_do_nothing(constraint="uq_recommendation_alert_rule")
                .returning(Recommendation.recommendation_id)
            )
            creees += len((await self._session.scalars(requete)).all())
        return creees
