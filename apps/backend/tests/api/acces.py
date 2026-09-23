# Pourquoi : classification unique des routes du contrat, lue par test_route_protection.py,
# test_openapi.py et test_matrice_acces.py. Trois listes séparées dérivaient auparavant chacune
# de leur côté, et deux entrées de ROUTES_A_ROLE ne correspondaient plus à aucune route sans que
# rien ne le signale.
# Piège : les trois ensembles doivent rester disjoints et couvrir tout le schéma. C'est
# `test_every_declared_route_is_classified` qui le vérifie, pas la relecture.

from typing import Final

from app.core.roles import Role

Route = tuple[str, str]

ROUTES_PUBLIQUES: Final[frozenset[Route]] = frozenset(
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

# Le cookie opaque porte seul l'autorisation : sans lui la route rend 401, mais aucun `Principal`
# n'est construit et `require_role` n'entre jamais en jeu.
ROUTE_COOKIE: Final[frozenset[Route]] = frozenset({("POST", "/api/v1/auth/refresh")})

# Authentifiées par `CurrentPrincipalDep` nu, donc hors de `require_role` et, avec lui, hors du
# refus `password_change_required`. Volontaire pour `/auth/password`, qui est la sortie de l'état
# provisoire ; subi pour `/auth/logout-all`, cf. test_matrice_acces.py.
ROUTES_SANS_ROLE: Final[frozenset[Route]] = frozenset(
    {
        ("GET", "/api/v1/auth/me"),
        ("POST", "/api/v1/auth/password"),
        ("POST", "/api/v1/auth/logout-all"),
    }
)

ROLE_MINIMUM: Final[dict[Route, Role]] = {
    ("GET", "/api/v1/sites"): Role.LECTEUR,
    ("GET", "/api/v1/sites/{site_id}"): Role.LECTEUR,
    ("GET", "/api/v1/sites/{site_id}/current"): Role.LECTEUR,
    ("GET", "/api/v1/alerts"): Role.LECTEUR,
    ("GET", "/api/v1/recommendations"): Role.LECTEUR,
    ("GET", "/api/v1/recommendations/{recommendation_id}"): Role.LECTEUR,
    ("POST", "/api/v1/recommendations/generate"): Role.ADMIN,
    ("GET", "/api/v1/stats/summary"): Role.LECTEUR,
    ("GET", "/api/v1/readings"): Role.LECTEUR,
    ("GET", "/api/v1/predictions"): Role.LECTEUR,
    ("GET", "/api/v1/sensors/status"): Role.ADMIN,
    ("GET", "/api/v1/monitoring/drift"): Role.OPERATEUR,
    ("GET", "/api/v1/users"): Role.ADMIN,
    ("POST", "/api/v1/users"): Role.ADMIN,
    ("PATCH", "/api/v1/users/{user_id}"): Role.ADMIN,
    ("POST", "/api/v1/users/{user_id}/password-reset"): Role.ADMIN,
}

# Piège : `{recommendation_id}` est typé `int` et `{user_id}` est un UUID. Une substitution
# uniforme par une chaîne quelconque rendrait 422 avant d'atteindre la garde de rôle, et le test
# passerait en prouvant autre chose que ce qu'il annonce.
SUBSTITUTIONS: Final[dict[str, str]] = {
    "{user_id}": "00000000-0000-0000-0000-000000000000",
    "{site_id}": "site-absent-du-jeu-de-donnees",
    "{recommendation_id}": "999999999",
}


def chemin_concret(chemin: str) -> str:
    for gabarit, valeur in SUBSTITUTIONS.items():
        chemin = chemin.replace(gabarit, valeur)
    return chemin


def routes_du_schema(schema: dict[str, object]) -> list[Route]:
    chemins: dict[str, dict[str, object]] = schema["paths"]  # type: ignore[assignment]
    return [
        (methode.upper(), chemin)
        for chemin, operations in chemins.items()
        for methode in operations
        if methode.upper() in {"GET", "POST", "PATCH", "PUT", "DELETE"}
    ]
