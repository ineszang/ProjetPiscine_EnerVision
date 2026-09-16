from datetime import UTC, datetime

import pytest

from app.models.energy import Recommendation
from app.services.recommendation import RecommendationNotFoundError, RecommendationService


def recommendation(recommendation_id: int = 1) -> Recommendation:
    return Recommendation(
        recommendation_id=recommendation_id,
        alert_id=1,
        action="Vérifier la consommation",
        explanation="Pic détecté",
        rule_reference="spike-v1",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
    )


class FakeRepository:
    def __init__(self, recommendations: list[Recommendation]) -> None:
        self._recommendations = recommendations

    async def list_all(self) -> list[Recommendation]:
        return self._recommendations

    async def get_by_id(self, recommendation_id: int) -> Recommendation | None:
        return next(
            (r for r in self._recommendations if r.recommendation_id == recommendation_id), None
        )


async def test_list_all_returns_the_repository_recommendations() -> None:
    service = RecommendationService(
        recommendations=FakeRepository([recommendation(1), recommendation(2)])
    )

    recommendations = await service.list_all()

    assert [r.recommendation_id for r in recommendations] == [1, 2]


async def test_get_by_id_returns_the_matching_recommendation() -> None:
    service = RecommendationService(recommendations=FakeRepository([recommendation(1)]))

    trouve = await service.get_by_id(1)

    assert trouve.recommendation_id == 1


async def test_get_by_id_raises_when_the_recommendation_is_unknown() -> None:
    service = RecommendationService(recommendations=FakeRepository([]))

    with pytest.raises(RecommendationNotFoundError):
        await service.get_by_id(404)
