from collections.abc import Callable, Iterator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import AdminDep, get_current_principal, require_role
from app.core.principal import Principal
from app.core.roles import AccountKind, Role

CHEMIN_ADMIN = "/api/v1/essai-admin"


def principal(role: Role = Role.LECTEUR, *, must_change_password: bool = False) -> Principal:
    return Principal(
        id=uuid4(),
        email=f"{role.value}@enervision.fr",
        role=role,
        kind=AccountKind.HUMAIN,
        must_change_password=must_change_password,
    )


@pytest.fixture
def route_admin(app: FastAPI) -> None:
    @app.get(CHEMIN_ADMIN)
    async def _reserve_aux_admins(acteur: AdminDep) -> dict[str, str]:
        return {"email": acteur.email}


@pytest.fixture
def connecte(app: FastAPI) -> Iterator[Callable[[Principal], None]]:
    def installe(acteur: Principal) -> None:
        app.dependency_overrides[get_current_principal] = lambda: acteur

    yield installe
    app.dependency_overrides.pop(get_current_principal, None)


async def test_me_returns_401_when_no_credentials_are_sent(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert "Bearer" in response.headers["www-authenticate"]


async def test_me_returns_401_when_the_token_is_not_readable(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer nimporte.quoi.ici"}
    )

    assert response.status_code == 401
    assert 'error="invalid_token"' in response.headers["www-authenticate"]


async def test_me_describes_the_connected_account(
    connecte: Callable[[Principal], None], client: AsyncClient
) -> None:
    acteur = principal(Role.OPERATEUR)
    connecte(acteur)

    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == acteur.email


@pytest.mark.parametrize(
    ("role", "attendu"),
    [(Role.LECTEUR, 403), (Role.OPERATEUR, 403), (Role.ADMIN, 200)],
    ids=["lecteur_refuse", "operateur_refuse", "admin_accepte"],
)
async def test_an_admin_route_only_answers_to_an_admin(
    route_admin: None,
    connecte: Callable[[Principal], None],
    client: AsyncClient,
    role: Role,
    attendu: int,
) -> None:
    connecte(principal(role))

    response = await client.get(CHEMIN_ADMIN)

    assert response.status_code == attendu


async def test_a_pending_password_change_blocks_every_business_route(
    route_admin: None, connecte: Callable[[Principal], None], client: AsyncClient
) -> None:
    connecte(principal(Role.ADMIN, must_change_password=True))

    response = await client.get(CHEMIN_ADMIN)

    assert response.status_code == 403
    assert response.json()["detail"] == "password_change_required"


async def test_a_pending_password_change_still_allows_reading_ones_own_account(
    connecte: Callable[[Principal], None], client: AsyncClient
) -> None:
    connecte(principal(Role.LECTEUR, must_change_password=True))

    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["must_change_password"] is True


def test_require_role_builds_one_guard_per_minimum_level() -> None:
    garde = require_role(Role.OPERATEUR)

    assert callable(garde)
