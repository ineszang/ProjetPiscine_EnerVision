# Pourquoi : `openapi.json` est versionné, donc une route qui change son contrat public le montre
# dans la diff d'une pull request. `test_the_committed_contract_matches_the_generated_one` est ce
# qui empêche le fichier de dériver du code sans que personne ne le voie.

import json
from typing import Any

import pytest

from app import cli

METHODES = {"get", "post", "patch", "put", "delete"}

# `/auth/logout` lit le cookie mais ne le réclame pas : sans session elle répond 204, et un 401
# documenté y serait faux.
SANS_REFUS = {("POST", "/api/v1/auth/logout")}

ORIGINE_VERIFIEE = {
    ("POST", "/api/v1/auth/refresh"),
    ("POST", "/api/v1/auth/logout"),
    ("POST", "/api/v1/auth/logout-all"),
    ("POST", "/api/v1/auth/password"),
}

# Toute route derrière `require_role` (LecteurDep, OperateurDep, AdminDep) peut rendre 403 pour
# `password_change_required`, pas seulement les routes `admin`.
ROUTES_A_ROLE = {
    ("GET", "/api/v1/users"),
    ("POST", "/api/v1/users"),
    ("PATCH", "/api/v1/users/{id}"),
    ("POST", "/api/v1/users/{id}/password-reset"),
    ("GET", "/api/v1/sites"),
    ("GET", "/api/v1/sites/{site_id}"),
    ("GET", "/api/v1/alerts"),
    ("GET", "/api/v1/recommendations"),
    ("GET", "/api/v1/recommendations/{recommendation_id}"),
    ("GET", "/api/v1/stats/summary"),
    ("GET", "/api/v1/readings"),
    ("GET", "/api/v1/sensors/status"),
    ("GET", "/api/v1/predictions"),
}


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return cli.schema_du_contrat()


def operations(schema: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (methode.upper(), chemin, operation)
        for chemin, operations_du_chemin in schema["paths"].items()
        for methode, operation in operations_du_chemin.items()
        if methode in METHODES
    ]


def test_the_committed_contract_matches_the_generated_one(schema: dict[str, Any]) -> None:
    publie = json.loads(cli.CHEMIN_CONTRAT.read_text(encoding="utf-8"))

    assert publie == schema, "lancer `make openapi` et versionner le fichier obtenu"


def test_every_route_demanding_an_identity_says_how_it_refuses(schema: dict[str, Any]) -> None:
    muettes = [
        (methode, chemin)
        for methode, chemin, operation in operations(schema)
        if operation.get("security")
        and (methode, chemin) not in SANS_REFUS
        and "401" not in operation["responses"]
    ]

    assert muettes == []


def test_every_role_guarded_route_documents_the_role_refusal(schema: dict[str, Any]) -> None:
    sans_403 = [
        (methode, chemin)
        for methode, chemin, operation in operations(schema)
        if (methode, chemin) in ROUTES_A_ROLE and "403" not in operation["responses"]
    ]

    assert sans_403 == []


def test_every_origin_checked_route_documents_the_csrf_refusal(schema: dict[str, Any]) -> None:
    sans_403 = [
        (methode, chemin)
        for methode, chemin, operation in operations(schema)
        if (methode, chemin) in ORIGINE_VERIFIEE and "403" not in operation["responses"]
    ]

    assert sans_403 == []


def test_the_validation_model_matches_what_the_handler_returns(schema: dict[str, Any]) -> None:
    modeles = {
        operation["responses"]["422"]["content"]["application/json"]["schema"]["$ref"]
        for _, _, operation in operations(schema)
        if "422" in operation["responses"]
    }

    assert modeles == {"#/components/schemas/ValidationErrorResponse"}
    assert "HTTPValidationError" not in schema["components"]["schemas"]


def test_the_rate_limit_documents_the_delay_header(schema: dict[str, Any]) -> None:
    trop_de_tentatives = schema["paths"]["/api/v1/auth/login"]["post"]["responses"]["429"]

    assert "Retry-After" in trop_de_tentatives["headers"]


def test_the_refresh_cookie_appears_in_the_security_schemes(schema: dict[str, Any]) -> None:
    schemes = schema["components"]["securitySchemes"]

    assert schemes["Cookie de rafraîchissement"]["in"] == "cookie"
    assert schemes["Cookie de rafraîchissement"]["name"] == "ev_refresh"


def test_each_tag_used_by_a_route_is_described(schema: dict[str, Any]) -> None:
    decrits = {tag["name"] for tag in schema["tags"]}

    for methode, chemin, operation in operations(schema):
        poses = operation.get("tags", [])
        assert len(poses) == len(set(poses)), f"tag en double sur {methode} {chemin}"
        assert set(poses) <= decrits, f"tag non décrit sur {methode} {chemin}"
