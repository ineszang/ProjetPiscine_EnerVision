from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_auth_service
from app.core.principal import Principal
from app.core.roles import AccountKind, Role
from app.services.auth import (
    AuthenticatedSession,
    InvalidCredentialsError,
    RateLimitedError,
)

IDENTIFIANTS = {"email": "operateur@enervision.fr", "password": "un-mot-de-passe-valide"}

PRINCIPAL = Principal(
    id=uuid4(),
    email="operateur@enervision.fr",
    role=Role.OPERATEUR,
    kind=AccountKind.HUMAIN,
    must_change_password=False,
)


class FauxService:
    def __init__(self, erreur: Exception | None = None) -> None:
        self._erreur = erreur

    async def authenticate(self, **_: object) -> AuthenticatedSession:
        if self._erreur is not None:
            raise self._erreur
        return AuthenticatedSession(
            principal=PRINCIPAL, access_token="un.jeton.factice", expires_in=900
        )


@pytest.fixture
def fake_auth_service(app: FastAPI) -> Iterator[list[Exception | None]]:
    programme: list[Exception | None] = [None]
    app.dependency_overrides[get_auth_service] = lambda: FauxService(programme[0])
    yield programme
    app.dependency_overrides.pop(get_auth_service, None)


async def test_login_returns_the_token_and_the_principal_when_credentials_match(
    fake_auth_service: list[Exception | None], client: AsyncClient
) -> None:
    response = await client.post("/api/v1/auth/login", json=IDENTIFIANTS)

    assert response.status_code == 200
    corps = response.json()
    assert corps["access_token"] == "un.jeton.factice"
    assert corps["token_type"] == "bearer"
    assert corps["principal"]["role"] == "operateur"


async def test_login_forbids_intermediaries_from_caching_the_response(
    fake_auth_service: list[Exception | None], client: AsyncClient
) -> None:
    response = await client.post("/api/v1/auth/login", json=IDENTIFIANTS)

    assert response.headers["cache-control"] == "no-store"


async def test_login_never_reveals_which_half_of_the_credentials_was_wrong(
    fake_auth_service: list[Exception | None], client: AsyncClient
) -> None:
    fake_auth_service[0] = InvalidCredentialsError("Identifiants invalides")

    response = await client.post("/api/v1/auth/login", json=IDENTIFIANTS)

    assert response.status_code == 401
    assert response.json() == {"detail": "Identifiants invalides"}


async def test_login_returns_429_with_a_retry_after_when_the_rate_limit_is_reached(
    fake_auth_service: list[Exception | None], client: AsyncClient
) -> None:
    fake_auth_service[0] = RateLimitedError(900)

    response = await client.post("/api/v1/auth/login", json=IDENTIFIANTS)

    assert response.status_code == 429
    assert response.headers["retry-after"] == "900"


@pytest.mark.parametrize(
    "corps",
    [
        {"email": "pas-une-adresse", "password": "un-mot-de-passe-valide"},
        {"email": "operateur@enervision.fr"},
        {"email": "operateur@enervision.fr", "password": "x" * 129},
    ],
    ids=["adresse_invalide", "mot_de_passe_absent", "mot_de_passe_trop_long"],
)
async def test_login_rejects_a_malformed_body_without_echoing_the_password(
    fake_auth_service: list[Exception | None], client: AsyncClient, corps: dict[str, str]
) -> None:
    response = await client.post("/api/v1/auth/login", json=corps)

    assert response.status_code == 422
    assert "un-mot-de-passe-valide" not in response.text
    assert "x" * 129 not in response.text
