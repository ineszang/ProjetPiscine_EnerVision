# Ce test est le garde-fou de l'autorisation : rendre une route publique oblige à modifier
# `ROUTES_PUBLIQUES` dans `tests/api/acces.py`, ce qui apparaît en clair dans la diff d'une pull
# request et demande une justification au relecteur.
# Pourquoi : il interroge réellement chaque route sans jeton au lieu d'inspecter l'arbre de
# dépendances. L'arbre n'est accessible que par l'API privée de FastAPI, et surtout une route
# peut porter la bonne dépendance tout en répondant quand même.

from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from tests.api.acces import (
    ROLE_MINIMUM,
    ROUTE_COOKIE,
    ROUTES_PUBLIQUES,
    ROUTES_SANS_ROLE,
    Route,
    chemin_concret,
    routes_du_schema,
)

STATUTS_DE_REFUS = {401, 403}
HORS_SCHEMA = {("GET", "/metrics")}


def routes_declarees(app: FastAPI) -> list[Route]:
    schema: dict[str, Any] = app.openapi()
    return routes_du_schema(schema)


def routes_protegees(app: FastAPI) -> list[Route]:
    return [route for route in routes_declarees(app) if route not in ROUTES_PUBLIQUES]


def test_the_public_allow_list_has_no_stale_entry(app: FastAPI) -> None:
    declarees = set(routes_declarees(app)) | HORS_SCHEMA

    inconnues = ROUTES_PUBLIQUES - declarees

    assert inconnues == set()


# Sans lui, une route ajoutée sans être classée n'est vue par aucun test de rôle : elle hérite
# du seul contrôle anonyme, et une garde posée au mauvais niveau passe inaperçue.
def test_every_declared_route_is_classified(app: FastAPI) -> None:
    classees = ROUTES_PUBLIQUES | ROUTE_COOKIE | ROUTES_SANS_ROLE | set(ROLE_MINIMUM)

    non_classees = set(routes_declarees(app)) - classees
    fantomes = classees - set(routes_declarees(app)) - HORS_SCHEMA

    assert non_classees == set(), "classer la route dans tests/api/acces.py"
    assert fantomes == set(), "entrée morte : la route n'existe plus sous ce chemin"


def test_the_four_classes_of_routes_stay_disjoint() -> None:
    classes = [ROUTES_PUBLIQUES, ROUTE_COOKIE, ROUTES_SANS_ROLE, frozenset(ROLE_MINIMUM)]

    for rang, classe in enumerate(classes):
        for autre in classes[rang + 1 :]:
            assert classe & autre == frozenset()


async def test_every_route_rejects_an_anonymous_caller_unless_explicitly_public(
    app: FastAPI, client: AsyncClient
) -> None:
    ouvertes: list[tuple[str, str, int]] = []

    for methode, chemin in routes_protegees(app):
        response = await client.request(methode, chemin_concret(chemin), json={})
        if response.status_code not in STATUTS_DE_REFUS:
            ouvertes.append((methode, chemin, response.status_code))

    assert ouvertes == []


async def test_the_declared_routes_are_actually_reachable(app: FastAPI) -> None:
    assert ("POST", "/api/v1/auth/login") in routes_declarees(app)
    assert ("GET", "/api/v1/auth/me") in routes_declarees(app)


@pytest.mark.parametrize(
    "chemin",
    ["/api/v1/health/live", "/api/v1/health/ready"],
    ids=["sonde_de_vie", "sonde_de_disponibilite"],
)
def test_the_health_probes_stay_public(app: FastAPI, chemin: str) -> None:
    assert ("GET", chemin) in ROUTES_PUBLIQUES


# Piège : ni les routes `include_in_schema=False` (/docs, /redoc) ni un `Mount` Starlette
# (/static) n'apparaissent dans `app.openapi()["paths"]`. `routes_declarees()` ne les voit
# donc jamais, et elles échapperaient silencieusement au garde-fou ci-dessus.
@pytest.mark.parametrize(
    "chemin",
    ["/docs", "/redoc", "/static/logo-icon.png"],
    ids=["swagger_ui", "redoc", "logo_statique"],
)
async def test_the_documentation_routes_are_public_by_design(
    app: FastAPI, client: AsyncClient, chemin: str
) -> None:
    response = await client.get(chemin)

    assert response.status_code == 200
