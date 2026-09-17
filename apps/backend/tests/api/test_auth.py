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
    InvalidOrExpiredResetTokenError,
    RateLimitedError,
    SessionRejectedError,
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
    def __init__(self, erreur: Exception | None = None, *, jeton_valide: bool = True) -> None:
        self._erreur = erreur
        self._jeton_valide = jeton_valide

    async def refresh(self, **_: object) -> AuthenticatedSession:
        return await self.authenticate()

    async def is_reset_token_valid(self, **_: object) -> bool:
        return self._jeton_valide

    async def logout(self, **_: object) -> None:
        return None

    async def request_password_reset(self, **_: object) -> None:
        if self._erreur is not None:
            raise self._erreur
        return None

    async def confirm_password_reset(self, **_: object) -> AuthenticatedSession:
        return await self.authenticate()

    async def authenticate(self, **_: object) -> AuthenticatedSession:
        if self._erreur is not None:
            raise self._erreur
        return AuthenticatedSession(
            principal=PRINCIPAL,
            access_token="un.jeton.factice",
            expires_in=900,
            refresh_secret="un-secret-opaque",
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


async def test_login_posts_an_http_only_refresh_cookie_scoped_to_the_auth_routes(
    fake_auth_service: list[Exception | None], client: AsyncClient
) -> None:
    response = await client.post("/api/v1/auth/login", json=IDENTIFIANTS)

    depose = response.headers["set-cookie"]
    assert depose.startswith("ev_refresh=un-secret-opaque")
    assert "HttpOnly" in depose
    assert "SameSite=strict" in depose
    assert "Path=/api/v1/auth" in depose


async def test_login_keeps_the_refresh_secret_out_of_the_response_body(
    fake_auth_service: list[Exception | None], client: AsyncClient
) -> None:
    response = await client.post("/api/v1/auth/login", json=IDENTIFIANTS)

    assert "un-secret-opaque" not in response.text


async def test_refresh_returns_401_when_no_cookie_is_presented(
    fake_auth_service: list[Exception | None], client: AsyncClient
) -> None:
    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 401


async def test_refresh_rotates_the_cookie_when_the_session_is_still_valid(
    fake_auth_service: list[Exception | None], client: AsyncClient
) -> None:
    client.cookies.set("ev_refresh", "un-secret-opaque")

    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 200
    assert "ev_refresh=" in response.headers["set-cookie"]


async def test_refresh_clears_the_cookie_when_the_session_is_rejected(
    fake_auth_service: list[Exception | None], client: AsyncClient
) -> None:
    fake_auth_service[0] = SessionRejectedError("Session révoquée")
    client.cookies.set("ev_refresh", "un-secret-rejoue")

    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    assert 'ev_refresh=""' in response.headers["set-cookie"]
    assert "Path=/api/v1/auth" in response.headers["set-cookie"]


async def test_logout_answers_204_and_clears_the_cookie(
    fake_auth_service: list[Exception | None], client: AsyncClient
) -> None:
    client.cookies.set("ev_refresh", "un-secret-opaque")

    response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    assert 'ev_refresh=""' in response.headers["set-cookie"]


async def test_logout_stays_idempotent_without_a_cookie(
    fake_auth_service: list[Exception | None], client: AsyncClient
) -> None:
    response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 204


@pytest.mark.parametrize(
    "chemin",
    ["/api/v1/auth/refresh", "/api/v1/auth/logout"],
    ids=["rotation", "deconnexion"],
)
async def test_a_cookie_bearing_route_refuses_a_foreign_origin(
    fake_auth_service: list[Exception | None], client: AsyncClient, chemin: str
) -> None:
    response = await client.post(chemin, headers={"Origin": "https://malveillant.example"})

    assert response.status_code == 403


async def test_a_cookie_bearing_route_accepts_a_request_without_origin(
    fake_auth_service: list[Exception | None], client: AsyncClient
) -> None:
    response = await client.post("/api/v1/auth/logout")

    assert response.status_code != 403


async def test_forgot_password_answers_202_when_the_account_exists(
    fake_auth_service: list[Exception | None], client: AsyncClient
) -> None:
    response = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "operateur@enervision.fr"}
    )

    assert response.status_code == 202
    assert response.headers["cache-control"] == "no-store"


async def test_forgot_password_answers_202_identically_when_the_account_is_unknown(
    fake_auth_service: list[Exception | None], client: AsyncClient
) -> None:
    response = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "inconnu@enervision.fr"}
    )

    assert response.status_code == 202


async def test_forgot_password_returns_429_with_a_retry_after_when_the_rate_limit_is_reached(
    fake_auth_service: list[Exception | None], client: AsyncClient
) -> None:
    fake_auth_service[0] = RateLimitedError(900)

    response = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "operateur@enervision.fr"}
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "900"


async def test_forgot_password_rejects_a_malformed_email(
    fake_auth_service: list[Exception | None], client: AsyncClient
) -> None:
    response = await client.post("/api/v1/auth/forgot-password", json={"email": "pas-un-email"})

    assert response.status_code == 422


@pytest.fixture
def fake_auth_service_reset_validity(app: FastAPI) -> Iterator[list[bool]]:
    programme = [True]
    app.dependency_overrides[get_auth_service] = lambda: FauxService(jeton_valide=programme[0])
    yield programme
    app.dependency_overrides.pop(get_auth_service, None)


async def test_validate_reset_token_reports_a_living_token(
    fake_auth_service_reset_validity: list[bool], client: AsyncClient
) -> None:
    response = await client.get(
        "/api/v1/auth/reset-password/validate", params={"token": "un-secret-opaque"}
    )

    assert response.status_code == 200
    assert response.json() == {"valid": True}


async def test_validate_reset_token_reports_an_invalid_or_expired_token(
    fake_auth_service_reset_validity: list[bool], client: AsyncClient
) -> None:
    fake_auth_service_reset_validity[0] = False

    response = await client.get(
        "/api/v1/auth/reset-password/validate", params={"token": "un-secret-perime"}
    )

    assert response.status_code == 200
    assert response.json() == {"valid": False}


async def test_reset_password_returns_the_token_and_the_cookie_on_success(
    fake_auth_service: list[Exception | None], client: AsyncClient
) -> None:
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "un-secret-opaque", "new_password": "Un-nouveau-mot-de-passe1!"},
    )

    assert response.status_code == 200
    assert response.cookies.get("ev_refresh") is not None
    assert "refresh_secret" not in response.text


async def test_reset_password_rejects_an_invalid_or_expired_token(
    fake_auth_service: list[Exception | None], client: AsyncClient
) -> None:
    fake_auth_service[0] = InvalidOrExpiredResetTokenError("Lien invalide ou expiré")

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "un-secret-perime", "new_password": "Un-nouveau-mot-de-passe1!"},
    )

    assert response.status_code == 400


async def test_reset_password_rejects_a_weak_password(
    fake_auth_service: list[Exception | None], client: AsyncClient
) -> None:
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "un-secret-opaque", "new_password": "trop-simple"},
    )

    assert response.status_code == 422


async def test_reset_password_refuses_a_foreign_origin(
    fake_auth_service: list[Exception | None], client: AsyncClient
) -> None:
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "un-secret-opaque", "new_password": "Un-nouveau-mot-de-passe1!"},
        headers={"Origin": "https://malveillant.example"},
    )

    assert response.status_code == 403
