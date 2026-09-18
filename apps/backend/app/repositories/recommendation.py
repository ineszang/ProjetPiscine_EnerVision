from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import Recommendation


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
