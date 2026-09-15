# Parcours complet contre la vraie base, sans serveur ni port ouvert. C'est ce fichier qui
# prouve que le câblage tient : la connexion, la rotation, la détection de réutilisation et la
# révocation immédiate passent par les vrais dépôts, les vraies transactions et les vrais
# déclencheurs PostgreSQL.

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.hashing import build_hasher
from app.core.roles import Role
from app.db.session import get_session_factory
from app.repositories.user import UserRepository

pytestmark = pytest.mark.integration

MOT_DE_PASSE = "un-mot-de-passe-de-recette"


@pytest.fixture
async def compte_operateur() -> AsyncIterator[str]:
    email = f"parcours-{uuid.uuid4().hex[:12]}@enervision.fr"
    hacheur = build_hasher(time_cost=1, memory_cost_kib=8192, parallelism=1, max_concurrency=2)
    empreinte = await hacheur.hash(MOT_DE_PASSE)

    async with get_session_factory()() as session:
        await UserRepository(session).create(
            email=email, password_hash=empreinte, role=Role.OPERATEUR
        )
        await session.commit()

    yield email

    async with get_session_factory()() as session:
        await session.execute(text("delete from app_user where email = :e"), {"e": email})
        await session.commit()


@pytest.fixture
async def navigateur(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def connecte(navigateur: AsyncClient, email: str) -> dict[str, str]:
    reponse = await navigateur.post(
        "/api/v1/auth/login", json={"email": email, "password": MOT_DE_PASSE}
    )
    assert reponse.status_code == 200, reponse.text
    return {"Authorization": f"Bearer {reponse.json()['access_token']}"}


async def test_a_full_session_runs_from_login_to_logout(
    compte_operateur: str, navigateur: AsyncClient
) -> None:
    entetes = await connecte(navigateur, compte_operateur)

    identite = await navigateur.get("/api/v1/auth/me", headers=entetes)
    rotation = await navigateur.post("/api/v1/auth/refresh")
    deconnexion = await navigateur.post("/api/v1/auth/logout")

    assert identite.status_code == 200
    assert identite.json()["role"] == "operateur"
    assert rotation.status_code == 200
    assert deconnexion.status_code == 204


async def test_replaying_a_rotated_cookie_kills_the_whole_family(
    compte_operateur: str, navigateur: AsyncClient
) -> None:
    await connecte(navigateur, compte_operateur)
    vole = navigateur.cookies["ev_refresh"]
    premiere_rotation = await navigateur.post("/api/v1/auth/refresh")
    vivant = navigateur.cookies["ev_refresh"]

    navigateur.cookies.set("ev_refresh", vole)
    rejeu = await navigateur.post("/api/v1/auth/refresh")

    navigateur.cookies.set("ev_refresh", vivant)
    apres = await navigateur.post("/api/v1/auth/refresh")

    assert premiere_rotation.status_code == 200
    assert rejeu.status_code == 401
    assert apres.status_code == 401, "la session vivante doit tomber avec sa famille"


async def test_the_reuse_leaves_a_trace_in_the_append_only_audit_log(
    compte_operateur: str, navigateur: AsyncClient
) -> None:
    await connecte(navigateur, compte_operateur)
    vole = navigateur.cookies["ev_refresh"]
    await navigateur.post("/api/v1/auth/refresh")

    navigateur.cookies.set("ev_refresh", vole)
    await navigateur.post("/api/v1/auth/refresh")

    async with get_session_factory()() as session:
        traces = await session.scalar(
            text("select count(*) from audit_log where action = 'auth.refresh_reuse_detected'")
        )
    assert traces is not None
    assert traces >= 1


async def test_disabling_an_account_invalidates_its_access_token_at_once(
    compte_operateur: str, navigateur: AsyncClient
) -> None:
    entetes = await connecte(navigateur, compte_operateur)
    avant = await navigateur.get("/api/v1/auth/me", headers=entetes)

    async with get_session_factory()() as session:
        depot = UserRepository(session)
        compte = await depot.get_by_email(compte_operateur)
        assert compte is not None
        await depot.set_active(compte.id, is_active=False)
        await session.commit()

    apres = await navigateur.get("/api/v1/auth/me", headers=entetes)

    assert avant.status_code == 200
    assert apres.status_code == 401, "la révocation doit être immédiate, pas dans 15 minutes"


async def test_changing_a_role_invalidates_the_token_that_still_carries_the_old_one(
    compte_operateur: str, navigateur: AsyncClient
) -> None:
    entetes = await connecte(navigateur, compte_operateur)

    async with get_session_factory()() as session:
        depot = UserRepository(session)
        compte = await depot.get_by_email(compte_operateur)
        assert compte is not None
        await depot.set_role(compte.id, Role.LECTEUR)
        await session.commit()

    apres = await navigateur.get("/api/v1/auth/me", headers=entetes)

    assert apres.status_code == 401
    assert "token_stale" in apres.headers["www-authenticate"]


async def test_a_failed_login_is_recorded_even_for_an_unknown_address(
    navigateur: AsyncClient,
) -> None:
    inconnu = f"inconnu-{uuid.uuid4().hex[:12]}@enervision.fr"

    reponse = await navigateur.post(
        "/api/v1/auth/login", json={"email": inconnu, "password": "peu-importe-ici"}
    )

    async with get_session_factory()() as session:
        tentatives = await session.scalar(
            text("select count(*) from login_attempt where email_tried = :e"), {"e": inconnu}
        )
    assert reponse.status_code == 401
    assert reponse.json() == {"detail": "Identifiants invalides"}
    assert tentatives == 1, "sans cette ligne, le 429 deviendrait un oracle d'existence"
