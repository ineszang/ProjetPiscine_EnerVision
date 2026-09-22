# Pourquoi : la matrice rôle x route sur les routes réelles. `test_authorization.py` la joue déjà,
# mais contre une route jetable montée par une fixture, ce qui ne dit rien du niveau effectivement
# posé sur `/sites` ou `/users`. `ROLE_MINIMUM` (tests/api/acces.py) est la référence, et ce
# fichier est ce qui la confronte au comportement observé.
# Piège : l'assertion porte sur le refus de la garde, pas sur un 200. Un rôle suffisant peut
# légitimement recevoir 404 ou 422 selon les données ; ce qui compte est qu'il ne reçoive pas le
# 403 `Droits insuffisants`. Sans cette nuance, le test dépendrait du contenu de la base.
# Les tests `integration` en fin de fichier rejouent la même matrice avec de vrais jetons, donc en
# traversant le décodage du JWT et la relecture du compte, ce que l'override court-circuite.

import uuid
from collections.abc import AsyncIterator, Callable, Iterator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response
from sqlalchemy import text

from app.api.deps import get_current_principal
from app.core.hashing import build_hasher
from app.core.principal import Principal
from app.core.roles import AccountKind, Role, has_at_least
from app.db.session import get_session, get_session_factory
from app.repositories.user import UserRepository
from tests.api.acces import ROLE_MINIMUM, chemin_concret

ROLES = [Role.LECTEUR, Role.OPERATEUR, Role.ADMIN]
IDS_DE_ROLE = ["lecteur", "operateur", "admin"]
REFUS_DE_DROITS = "Droits insuffisants"
REFUS_DE_MOT_DE_PASSE = "password_change_required"
MOT_DE_PASSE = "un-mot-de-passe-de-recette"


# `FakeSession` de tests/factories.py rend un unique objet pour les trois formes d'appel, ce qui
# suffit à un test d'endpoint ciblé mais pas à balayer 13 routes qui interrogent chacune la base
# à sa façon. Ce double rend un résultat vide quelle que soit la forme demandée, pour que la
# réponse observée vienne de la garde de rôle et jamais d'un double mal ajusté.
class ResultatVide:
    def scalars(self) -> ResultatVide:
        return self

    def all(self) -> list[object]:
        return []

    def first(self) -> None:
        return None

    def one_or_none(self) -> None:
        return None

    def scalar_one_or_none(self) -> None:
        return None

    def mappings(self) -> ResultatVide:
        return self

    def __iter__(self) -> Iterator[object]:
        return iter(())


class SessionMuette:
    async def scalar(self, *_: object, **__: object) -> None:
        return None

    async def execute(self, *_: object, **__: object) -> ResultatVide:
        return ResultatVide()

    async def scalars(self, *_: object, **__: object) -> ResultatVide:
        return ResultatVide()

    async def get(self, *_: object, **__: object) -> None:
        return None

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    def add(self, *_: object, **__: object) -> None:
        return None


@pytest.fixture
def base_muette(app: FastAPI) -> None:
    async def override() -> AsyncIterator[SessionMuette]:
        yield SessionMuette()

    app.dependency_overrides[get_session] = override


def principal(role: Role, *, must_change_password: bool = False) -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email=f"matrice-{role.value}@enervision.fr",
        role=role,
        kind=AccountKind.HUMAIN,
        must_change_password=must_change_password,
    )


@pytest.fixture
def connecte(app: FastAPI) -> Iterator[Callable[[Principal], None]]:
    def installe(acteur: Principal) -> None:
        app.dependency_overrides[get_current_principal] = lambda: acteur

    yield installe
    app.dependency_overrides.pop(get_current_principal, None)


async def appelle(client: AsyncClient, methode: str, chemin: str, **kwargs: object) -> Response:
    return await client.request(methode, chemin_concret(chemin), json={}, **kwargs)  # type: ignore[arg-type]


def motif_du_refus(response: Response) -> str | None:
    if response.status_code != 403:
        return None
    detail = response.json().get("detail")
    return detail if isinstance(detail, str) else None


@pytest.mark.parametrize("role", ROLES, ids=IDS_DE_ROLE)
async def test_a_role_below_the_minimum_is_refused_on_every_guarded_route(
    connecte: Callable[[Principal], None],
    client: AsyncClient,
    base_muette: None,
    role: Role,
) -> None:
    connecte(principal(role))
    laissees_passer: list[tuple[str, str, int]] = []

    for (methode, chemin), minimum in ROLE_MINIMUM.items():
        if has_at_least(role, minimum):
            continue
        response = await appelle(client, methode, chemin)
        if motif_du_refus(response) != REFUS_DE_DROITS:
            laissees_passer.append((methode, chemin, response.status_code))

    assert laissees_passer == []


# Le pendant du test précédent : sans lui, une garde posée trop haut, par exemple `AdminDep` sur
# `/sites`, ne ferait échouer aucun test du dépôt.
@pytest.mark.parametrize("role", ROLES, ids=IDS_DE_ROLE)
async def test_a_role_at_or_above_the_minimum_is_never_refused_by_the_guard(
    connecte: Callable[[Principal], None],
    client: AsyncClient,
    base_muette: None,
    role: Role,
) -> None:
    connecte(principal(role))
    refusees: list[tuple[str, str]] = []

    for (methode, chemin), minimum in ROLE_MINIMUM.items():
        if not has_at_least(role, minimum):
            continue
        response = await appelle(client, methode, chemin)
        if motif_du_refus(response) == REFUS_DE_DROITS:
            refusees.append((methode, chemin))

    assert refusees == []


async def test_a_pending_password_change_is_refused_on_every_guarded_route(
    connecte: Callable[[Principal], None],
    client: AsyncClient,
    base_muette: None,
) -> None:
    connecte(principal(Role.ADMIN, must_change_password=True))
    laissees_passer: list[tuple[str, str, int]] = []

    for methode, chemin in ROLE_MINIMUM:
        response = await appelle(client, methode, chemin)
        if motif_du_refus(response) != REFUS_DE_MOT_DE_PASSE:
            laissees_passer.append((methode, chemin, response.status_code))

    assert laissees_passer == []


@pytest.fixture
async def comptes_par_role() -> AsyncIterator[dict[Role, str]]:
    marque = uuid.uuid4().hex[:12]
    hacheur = build_hasher(time_cost=1, memory_cost_kib=8192, parallelism=1, max_concurrency=2)
    empreinte = await hacheur.hash(MOT_DE_PASSE)
    adresses = {role: f"matrice-{marque}-{role.value}@enervision.fr" for role in ROLES}

    async with get_session_factory()() as session:
        depot = UserRepository(session)
        for role, email in adresses.items():
            await depot.create(email=email, password_hash=empreinte, role=role)
        await session.commit()

    yield adresses

    async with get_session_factory()() as session:
        await session.execute(
            text("delete from app_user where email like :motif"), {"motif": f"matrice-{marque}-%"}
        )
        await session.commit()


async def authentifie(client: AsyncClient, email: str) -> dict[str, str]:
    reponse = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": MOT_DE_PASSE}
    )
    assert reponse.status_code == 200, reponse.text
    return {"Authorization": f"Bearer {reponse.json()['access_token']}"}


@pytest.mark.integration
@pytest.mark.parametrize("role", ROLES, ids=IDS_DE_ROLE)
async def test_a_real_token_reaches_exactly_the_routes_of_its_rank(
    comptes_par_role: dict[Role, str], client: AsyncClient, role: Role
) -> None:
    entetes = await authentifie(client, comptes_par_role[role])
    ecarts: list[tuple[str, str, int, str]] = []

    for (methode, chemin), minimum in ROLE_MINIMUM.items():
        response = await appelle(client, methode, chemin, headers=entetes)
        refuse = motif_du_refus(response) == REFUS_DE_DROITS
        if refuse is has_at_least(role, minimum):
            ecarts.append((methode, chemin, response.status_code, response.text[:120]))

    assert ecarts == []


# Contrainte : les deux rangs ne se séparent que sur les routes que `ROLE_MINIMUM` réserve à
# `operateur`. Une route d'opérateur ajoutée sans être classée fait diverger les statuts sans
# qu'aucune entrée ne l'annonce, et une garde d'opérateur posée par erreur sur une route de
# lecture fait diverger ce qui devait rester identique.
@pytest.mark.integration
async def test_the_operator_rank_diverges_from_the_reader_rank_only_where_declared(
    comptes_par_role: dict[Role, str], client: AsyncClient
) -> None:
    lecteur = await authentifie(client, comptes_par_role[Role.LECTEUR])
    operateur = await authentifie(client, comptes_par_role[Role.OPERATEUR])
    ecarts: list[tuple[str, str]] = []

    for (methode, chemin), minimum in ROLE_MINIMUM.items():
        cote_lecteur = await appelle(client, methode, chemin, headers=lecteur)
        cote_operateur = await appelle(client, methode, chemin, headers=operateur)
        diverge = cote_lecteur.status_code != cote_operateur.status_code
        if diverge is not (minimum is Role.OPERATEUR):
            ecarts.append((methode, chemin))

    assert ecarts == []


# Piège : `/auth/logout-all` prend un `CurrentPrincipalDep` nu, donc elle échappe au gate
# `must_change_password` que seul `require_role` applique. Comportement figé ici, pas corrigé.
@pytest.mark.integration
async def test_a_temporary_password_blocks_the_business_routes_but_not_logout_all(
    client: AsyncClient,
) -> None:
    marque = uuid.uuid4().hex[:12]
    email = f"matrice-{marque}-provisoire@enervision.fr"
    hacheur = build_hasher(time_cost=1, memory_cost_kib=8192, parallelism=1, max_concurrency=2)
    empreinte = await hacheur.hash(MOT_DE_PASSE)

    async with get_session_factory()() as session:
        await UserRepository(session).create(
            email=email, password_hash=empreinte, role=Role.ADMIN, must_change_password=True
        )
        await session.commit()

    try:
        entetes = await authentifie(client, email)
        sites = await client.get("/api/v1/sites", headers=entetes)
        identite = await client.get("/api/v1/auth/me", headers=entetes)
        fermeture = await client.post("/api/v1/auth/logout-all", headers=entetes)

        assert motif_du_refus(sites) == REFUS_DE_MOT_DE_PASSE
        assert identite.status_code == 200
        assert fermeture.status_code == 204
    finally:
        async with get_session_factory()() as session:
            await session.execute(text("delete from app_user where email = :e"), {"e": email})
            await session.commit()
