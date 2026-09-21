from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_current_principal, get_recommendation_service
from app.core.principal import Principal
from app.core.roles import AccountKind, Role
from app.models.energy import Recommendation
from app.services.recommendation import RapportGeneration, RecommendationNotFoundError

MOMENT = datetime(2024, 1, 1, tzinfo=UTC)


def principal(role: Role = Role.LECTEUR) -> Principal:
    return Principal(
        id=uuid4(),
        email=f"{role.value}@enervision.fr",
        role=role,
        kind=AccountKind.HUMAIN,
        must_change_password=False,
    )


def recommendation(recommendation_id: int = 1) -> Recommendation:
    return Recommendation(
        recommendation_id=recommendation_id,
        alert_id=1,
        action="Vérifier la consommation",
        explanation="Pic détecté",
        rule_reference="spike-v1",
        created_at=MOMENT,
    )


class FauxService:
    def __init__(self, erreur: Exception | None = None) -> None:
        self._erreur = erreur
        self.recommendation = recommendation()
        self.site_demande: str | None = None

    async def list_all(self) -> list[Recommendation]:
        return [self.recommendation]

    async def get_by_id(self, recommendation_id: int) -> Recommendation:
        if self._erreur is not None:
            raise self._erreur
        return self.recommendation

    async def generate(self, *, site_id: str | None = None) -> RapportGeneration:
        self.site_demande = site_id
        return RapportGeneration(alertes_examinees=2, recommandations_creees=3, deja_presentes=1)


@pytest.fixture
def lecteur_connecte(app: FastAPI) -> Iterator[None]:
    app.dependency_overrides[get_current_principal] = lambda: principal()
    yield
    app.dependency_overrides.pop(get_current_principal, None)


@pytest.fixture
def servi(
    app: FastAPI, lecteur_connecte: None
) -> Iterator[Callable[[Exception | None], FauxService]]:
    def installe(erreur: Exception | None = None) -> FauxService:
        service = FauxService(erreur)
        app.dependency_overrides[get_recommendation_service] = lambda: service
        return service

    yield installe
    app.dependency_overrides.pop(get_recommendation_service, None)


async def test_list_recommendations_returns_the_recommendations(
    servi: Callable[..., FauxService], client: AsyncClient
) -> None:
    servi()

    response = await client.get("/api/v1/recommendations")

    assert response.status_code == 200
    corps = response.json()
    assert corps == [
        {
            "recommendation_id": 1,
            "alert_id": 1,
            "action": "Vérifier la consommation",
            "explanation": "Pic détecté",
            "rule_reference": "spike-v1",
            "created_at": "2024-01-01T00:00:00Z",
        }
    ]


async def test_get_recommendation_returns_the_matching_recommendation(
    servi: Callable[..., FauxService], client: AsyncClient
) -> None:
    servi()

    response = await client.get("/api/v1/recommendations/1")

    assert response.status_code == 200
    assert response.json()["recommendation_id"] == 1


async def test_get_recommendation_returns_404_for_an_unknown_recommendation(
    servi: Callable[..., FauxService], client: AsyncClient
) -> None:
    servi(RecommendationNotFoundError(404))

    response = await client.get("/api/v1/recommendations/404")

    assert response.status_code == 404


async def test_list_recommendations_reaches_the_repository_through_the_session(
    lecteur_connecte: None, fake_session: Callable[..., None], client: AsyncClient
) -> None:
    fake_session(result=[recommendation(1), recommendation(2)])

    response = await client.get("/api/v1/recommendations")

    assert response.status_code == 200
    assert [r["recommendation_id"] for r in response.json()] == [1, 2]


async def test_get_recommendation_reaches_the_repository_through_the_session(
    lecteur_connecte: None, fake_session: Callable[..., None], client: AsyncClient
) -> None:
    fake_session(result=recommendation(1))

    response = await client.get("/api/v1/recommendations/1")

    assert response.status_code == 200
    assert response.json()["recommendation_id"] == 1


async def test_get_recommendation_returns_404_when_the_session_finds_nothing(
    lecteur_connecte: None, fake_session: Callable[..., None], client: AsyncClient
) -> None:
    fake_session(result=None)

    response = await client.get("/api/v1/recommendations/404")

    assert response.status_code == 404


@pytest.fixture
def admin_connecte(app: FastAPI) -> Iterator[None]:
    app.dependency_overrides[get_current_principal] = lambda: principal(Role.ADMIN)
    yield
    app.dependency_overrides.pop(get_current_principal, None)


@pytest.fixture
def servi_en_admin(app: FastAPI, admin_connecte: None) -> Iterator[Callable[[], FauxService]]:
    def installe() -> FauxService:
        service = FauxService()
        app.dependency_overrides[get_recommendation_service] = lambda: service
        return service

    yield installe
    app.dependency_overrides.pop(get_recommendation_service, None)


async def test_generate_recommendations_returns_the_generation_report(
    servi_en_admin: Callable[[], FauxService], client: AsyncClient
) -> None:
    servi_en_admin()

    response = await client.post("/api/v1/recommendations/generate")

    assert response.status_code == 200
    assert response.json() == {
        "alerts_examined": 2,
        "recommendations_created": 3,
        "already_present": 1,
    }


async def test_generate_recommendations_forwards_the_requested_site(
    servi_en_admin: Callable[[], FauxService], client: AsyncClient
) -> None:
    service = servi_en_admin()

    await client.post("/api/v1/recommendations/generate", params={"site_id": "SITE002"})

    assert service.site_demande == "SITE002"


async def test_generate_recommendations_refuses_a_reader(
    servi: Callable[..., FauxService], client: AsyncClient
) -> None:
    servi()

    response = await client.post("/api/v1/recommendations/generate")

    assert response.status_code == 403
