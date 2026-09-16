from collections.abc import Callable, Iterator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_current_principal, get_site_service
from app.core.principal import Principal
from app.core.roles import AccountKind, Role
from app.models.energy import Site
from app.services.site import SiteNotFoundError


def principal(role: Role = Role.LECTEUR) -> Principal:
    return Principal(
        id=uuid4(),
        email=f"{role.value}@enervision.fr",
        role=role,
        kind=AccountKind.HUMAIN,
        must_change_password=False,
    )


def site(site_id: str = "site-1") -> Site:
    return Site(
        site_id=site_id,
        site_name="Site de test",
        site_type="industriel",
        location="Toulouse",
        capacity_kw=42.0,
        status="actif",
    )


class FauxService:
    def __init__(self, erreur: Exception | None = None) -> None:
        self._erreur = erreur
        self.site = site()

    async def list_all(self) -> list[Site]:
        return [self.site]

    async def get_by_id(self, site_id: str) -> Site:
        if self._erreur is not None:
            raise self._erreur
        return self.site


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
        app.dependency_overrides[get_site_service] = lambda: service
        return service

    yield installe
    app.dependency_overrides.pop(get_site_service, None)


async def test_list_sites_returns_the_sites(
    servi: Callable[..., FauxService], client: AsyncClient
) -> None:
    servi()

    response = await client.get("/api/v1/sites")

    assert response.status_code == 200
    corps = response.json()
    assert corps == [
        {
            "site_id": "site-1",
            "site_name": "Site de test",
            "site_type": "industriel",
            "location": "Toulouse",
            "capacity_kw": 42.0,
            "status": "actif",
        }
    ]


async def test_get_site_returns_the_matching_site(
    servi: Callable[..., FauxService], client: AsyncClient
) -> None:
    servi()

    response = await client.get("/api/v1/sites/site-1")

    assert response.status_code == 200
    assert response.json()["site_id"] == "site-1"


async def test_get_site_returns_404_for_an_unknown_site(
    servi: Callable[..., FauxService], client: AsyncClient
) -> None:
    servi(SiteNotFoundError("site-inconnu"))

    response = await client.get("/api/v1/sites/site-inconnu")

    assert response.status_code == 404


async def test_list_sites_reaches_the_repository_through_the_session(
    lecteur_connecte: None, fake_session: Callable[..., None], client: AsyncClient
) -> None:
    fake_session(result=[site("a"), site("b")])

    response = await client.get("/api/v1/sites")

    assert response.status_code == 200
    assert [s["site_id"] for s in response.json()] == ["a", "b"]


async def test_get_site_reaches_the_repository_through_the_session(
    lecteur_connecte: None, fake_session: Callable[..., None], client: AsyncClient
) -> None:
    fake_session(result=site("a"))

    response = await client.get("/api/v1/sites/a")

    assert response.status_code == 200
    assert response.json()["site_id"] == "a"


async def test_get_site_returns_404_when_the_session_finds_nothing(
    lecteur_connecte: None, fake_session: Callable[..., None], client: AsyncClient
) -> None:
    fake_session(result=None)

    response = await client.get("/api/v1/sites/inconnu")

    assert response.status_code == 404
