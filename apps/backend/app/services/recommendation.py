from collections.abc import Sequence

from app.models.energy import Recommendation
from app.repositories.recommendation import RecommendationRepository


class RecommendationError(Exception):
    pass


class RecommendationNotFoundError(RecommendationError):
    pass


class RecommendationService:
    def __init__(self, *, recommendations: RecommendationRepository) -> None:
        self._recommendations = recommendations

    async def list_all(self) -> Sequence[Recommendation]:
        return await self._recommendations.list_all()

    async def get_by_id(self, recommendation_id: int) -> Recommendation:
        recommendation = await self._recommendations.get_by_id(recommendation_id)
        if recommendation is None:
            raise RecommendationNotFoundError(recommendation_id)
        return recommendation
