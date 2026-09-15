from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_current_principal, get_user_service
from app.core.principal import Principal
from app.core.roles import AccountKind, Role
from app.services.user import CreatedUser, EmailAlreadyUsedError, LastAdminError, UserNotFoundError


def principal(role: Role = Role.ADMIN) -> Principal:
    return Principal(
        id=uuid4(),
        email=f"{role.value}@enervision.fr",
        role=role,
        kind=AccountKind.HUMAIN,
        must_change_password=False,
    )


class FauxCompte:
    def __init__(self, role: Role = Role.LECTEUR) -> None:
        self.id = uuid4()
        self.email = "cible@enervision.fr"
        self.role = role.value
        self.kind = "human"
        self.is_active = True
        self.must_change_password = True
        self.full_name = None
        self.last_login_at: datetime | None = None
        self.created_at = datetime.now(UTC)


class FauxService:
    def __init__(self, erreur: Exception | None = None) -> None:
        self._erreur = erreur
        self.compte = FauxCompte()

    def _leve(self) -> None:
        if self._erreur is not None:
            raise self._erreur

    async def list_all(self) -> list[FauxCompte]:
        return [self.compte]

    async def create(self, **_: object) -> CreatedUser:
        self._leve()
        return CreatedUser(user=self.compte, temporary_password="mot-de-passe-provisoire")  # type: ignore[arg-type]

    async def change_role(self, **_: object) -> FauxCompte:
        self._leve()
        return self.compte

    async def set_active(self, **_: object) -> FauxCompte:
        self._leve()
        return self.compte

    async def reset_password(self, **_: object) -> CreatedUser:
        self._leve()
        return CreatedUser(user=self.compte, temporary_password="mot-de-passe-provisoire")  # type: ignore[arg-type]


@pytest.fixture
def administre(app: FastAPI) -> Iterator[Callable[[Exception | None], FauxService]]:
    services: list[FauxService] = []

    def installe(erreur: Exception | None = None) -> FauxService:
        service = FauxService(erreur)
        services.append(service)
        app.dependency_overrides[get_user_service] = lambda: service
        app.dependency_overrides[get_current_principal] = lambda: principal()
        return service

    yield installe
    app.dependency_overrides.pop(get_user_service, None)
    app.dependency_overrides.pop(get_current_principal, None)


@pytest.fixture
def lecteur_connecte(app: FastAPI) -> Iterator[None]:
    app.dependency_overrides[get_current_principal] = lambda: principal(Role.LECTEUR)
    yield
    app.dependency_overrides.pop(get_current_principal, None)


async def test_list_users_returns_the_accounts_without_their_digest(
    administre: Callable[..., FauxService], client: AsyncClient
) -> None:
    administre()

    response = await client.get("/api/v1/users")

    assert response.status_code == 200
    corps = response.json()
    assert "password_hash" not in corps[0]
    assert corps[0]["email"] == "cible@enervision.fr"


async def test_create_user_returns_the_temporary_password_once(
    administre: Callable[..., FauxService], client: AsyncClient
) -> None:
    administre()

    response = await client.post(
        "/api/v1/users", json={"email": "nouveau@enervision.fr", "role": "operateur"}
    )

    assert response.status_code == 201
    assert response.json()["temporary_password"] == "mot-de-passe-provisoire"
    assert response.headers["cache-control"] == "no-store"


async def test_create_user_refuses_an_address_already_taken(
    administre: Callable[..., FauxService], client: AsyncClient
) -> None:
    administre(EmailAlreadyUsedError("cible@enervision.fr"))

    response = await client.post(
        "/api/v1/users", json={"email": "cible@enervision.fr", "role": "lecteur"}
    )

    assert response.status_code == 409


async def test_create_user_never_accepts_a_caller_chosen_digest(
    administre: Callable[..., FauxService], client: AsyncClient
) -> None:
    administre()

    response = await client.post(
        "/api/v1/users",
        json={
            "email": "nouveau@enervision.fr",
            "role": "lecteur",
            "password_hash": "$argon2id$force",
            "is_active": False,
        },
    )

    assert response.status_code == 201


async def test_update_user_refuses_to_strand_the_last_administrator(
    administre: Callable[..., FauxService], client: AsyncClient
) -> None:
    administre(LastAdminError("x"))

    response = await client.patch(f"/api/v1/users/{uuid4()}", json={"is_active": False})

    assert response.status_code == 409


async def test_update_user_returns_404_for_an_unknown_account(
    administre: Callable[..., FauxService], client: AsyncClient
) -> None:
    administre(UserNotFoundError("x"))

    response = await client.patch(f"/api/v1/users/{uuid4()}", json={"role": "admin"})

    assert response.status_code == 404


async def test_update_user_refuses_an_empty_body(
    administre: Callable[..., FauxService], client: AsyncClient
) -> None:
    administre()

    response = await client.patch(f"/api/v1/users/{uuid4()}", json={})

    assert response.status_code == 400


async def test_reset_password_returns_a_new_temporary_password(
    administre: Callable[..., FauxService], client: AsyncClient
) -> None:
    administre()

    response = await client.post(f"/api/v1/users/{uuid4()}/password-reset")

    assert response.status_code == 200
    assert response.json()["temporary_password"] == "mot-de-passe-provisoire"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    ("methode", "chemin"),
    [
        ("GET", "/api/v1/users"),
        ("POST", "/api/v1/users"),
        ("PATCH", "/api/v1/users/{identifiant}"),
        ("POST", "/api/v1/users/{identifiant}/password-reset"),
    ],
    ids=["liste", "creation", "modification", "reinitialisation"],
)
async def test_every_administration_route_refuses_a_reader(
    lecteur_connecte: None, client: AsyncClient, methode: str, chemin: str
) -> None:
    identifiant: UUID = uuid4()

    response = await client.request(
        methode, chemin.format(identifiant=identifiant), json={"role": "admin"}
    )

    assert response.status_code == 403
