# Ce test est le garde-fou de l'autorisation : rendre une route publique oblige à modifier
# `ROUTES_PUBLIQUES` ci-dessous, ce qui apparaît en clair dans la diff d'une pull request et
# demande une justification au relecteur.
# Pourquoi : il interroge réellement chaque route sans jeton au lieu d'inspecter l'arbre de
# dépendances. L'arbre n'est accessible que par l'API privée de FastAPI, et surtout une route
# peut porter la bonne dépendance tout en répondant quand même.

from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

ROUTES_PUBLIQUES = frozenset(
    {
        ("GET", "/api/v1/health/live"),
        ("GET", "/api/v1/health/ready"),
        ("POST", "/api/v1/auth/login"),
        # Sans cookie, la déconnexion ne fait rien et répond 204 : elle est idempotente.
        ("POST", "/api/v1/auth/logout"),
        ("POST", "/api/v1/auth/forgot-password"),
        # Protégée par le jeton dans le corps de la requête, pas par un `Principal` : aucune
        # authentification préalable ne s'applique, c'est la validité du jeton qui tranche.
        ("POST", "/api/v1/auth/reset-password"),
        # Même raison : lecture seule, protégée par le jeton passé en paramètre, pas par un
        # `Principal`. Le jeton est un secret de 256 bits, non brute-forçable.
        ("GET", "/api/v1/auth/reset-password/validate"),
        ("GET", "/metrics"),
    }
)

VALEURS_DE_SUBSTITUTION = "00000000-0000-0000-0000-000000000000"
STATUTS_DE_REFUS = {401, 403}


def routes_declarees(app: FastAPI) -> list[tuple[str, str]]:
    schema: dict[str, Any] = app.openapi()
    return [
        (methode.upper(), chemin)
        for chemin, operations in schema["paths"].items()
        for methode in operations
        if methode.upper() in {"GET", "POST", "PATCH", "PUT", "DELETE"}
    ]


def routes_protegees(app: FastAPI) -> list[tuple[str, str]]:
    return [route for route in routes_declarees(app) if route not in ROUTES_PUBLIQUES]


def test_the_public_allow_list_has_no_stale_entry(app: FastAPI) -> None:
    declarees = set(routes_declarees(app)) | {("GET", "/metrics")}

    inconnues = ROUTES_PUBLIQUES - declarees

    assert inconnues == set()


async def test_every_route_rejects_an_anonymous_caller_unless_explicitly_public(
    app: FastAPI, client: AsyncClient
) -> None:
    ouvertes: list[tuple[str, str, int]] = []

    for methode, chemin in routes_protegees(app):
        concret = chemin.replace("{user_id}", VALEURS_DE_SUBSTITUTION)
        response = await client.request(methode, concret, json={})
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
