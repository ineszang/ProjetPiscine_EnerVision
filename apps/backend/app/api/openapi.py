# Piège : `cookie_de_rafraichissement` est purement documentaire, d'où son `auto_error=False`.
# Avec la valeur par défaut, FastAPI répondrait 403 avant d'atteindre `lit_le_cookie()`, et
# `/auth/refresh` cesserait de rendre le 401 que le frontend attend.

from typing import Any, Final

from fastapi.security import APIKeyCookie

from app.core.config import REFRESH_COOKIE_DEFAUT
from app.schemas.errors import ErrorResponse, InternalErrorResponse, ValidationErrorResponse

Reponses = dict[int | str, dict[str, Any]]

SUMMARY: Final = "Collecte, analyse et restitution de séries temporelles énergétiques."

DESCRIPTION: Final = """
Toutes les routes sont préfixées par `/api/v1`.

**Authentification.** Le jeton d'accès se présente dans l'en-tête `Authorization: Bearer ...`.
Le jeton de rafraîchissement est un cookie `HttpOnly` que le code client ne voit jamais : il
suffit d'émettre les requêtes avec les identifiants de session. `POST /auth/refresh` rend un
nouveau jeton d'accès et fait tourner le cookie.

**Rôles.** `lecteur`, puis `operateur`, puis `admin`. Chaque rôle couvre les droits du
précédent.

**Erreurs.** Le corps porte toujours une clé `detail`. Un `403` dont le `detail` vaut
`password_change_required` n'est pas un refus de droits : il exige le changement du mot de passe
provisoire avant toute autre action.

Le parcours de session complet est décrit dans
`docs/architecture/31-contrat-authentification.md`.
"""

TAGS: Final[list[dict[str, Any]]] = [
    {
        "name": "health",
        "description": (
            "Sondes d'infrastructure, publiques. `live` prouve que le processus répond, `ready` "
            "que la base répond et que l'extension TimescaleDB est chargée."
        ),
    },
    {
        "name": "auth",
        "description": (
            "Ouverture, rotation et fermeture de session, et changement de son propre mot de passe."
        ),
    },
    {
        "name": "users",
        "description": "Administration des comptes. Réservé au rôle `admin`.",
    },
    {
        "name": "sites",
        "description": "Consultation du parc de sites. Accessible à partir du rôle `lecteur`.",
    },
    {
        "name": "alerts",
        "description": "Consultation des alertes de consommation. Accessible à partir du rôle "
        "`lecteur`.",
    },
    {
        "name": "recommendations",
        "description": (
            "Consultation des recommandations issues des alertes. Accessible à partir du rôle "
            "`lecteur`."
        ),
    },
    {
        "name": "stats",
        "description": "Statistiques agrégées de consommation. Accessible à partir du rôle "
        "`lecteur`.",
    },
    {
        "name": "readings",
        "description": (
            "Historique des lectures de consommation. Fenêtre temporelle plafonnée à 90 jours, "
            "24 dernières heures par défaut si `start`/`end` sont omis. Accessible à partir du "
            "rôle `lecteur`."
        ),
    },
    {
        "name": "sensors",
        "description": "État de santé des capteurs par site. Réservé au rôle `admin`.",
    },
    {
        "name": "predictions",
        "description": (
            "Dernière prévision de consommation par site, calculée hors ligne par le pipeline "
            "de scoring (`ml/`) et simplement lue ici. Accessible à partir du rôle `lecteur`."
        ),
    },
]

cookie_de_rafraichissement = APIKeyCookie(
    name=REFRESH_COOKIE_DEFAUT,
    scheme_name="Cookie de rafraîchissement",
    description=(
        "Cookie `HttpOnly` posé par `/auth/login` et tourné par `/auth/refresh`. Il prend le "
        "préfixe `__Secure-` dès que l'API tourne derrière TLS, et n'est émis que vers "
        "`/api/v1/auth`."
    ),
    auto_error=False,
)

# Le 422 n'est déclaré que sur les routes qui acceptent un corps ou un paramètre : ailleurs,
# aucune validation ne peut échouer et l'annoncer serait faux.
REPONSE_VALIDATION: Final[Reponses] = {
    422: {
        "model": ValidationErrorResponse,
        "description": (
            "Corps invalide. Le détail nomme le champ fautif et le type d'erreur, jamais la "
            "valeur envoyée."
        ),
    },
}

REPONSE_SERVEUR: Final[Reponses] = {
    500: {
        "model": InternalErrorResponse,
        "description": (
            "Erreur interne. `correlation` identifie la trace côté serveur, qui n'est pas "
            "renvoyée au client."
        ),
    },
}

REPONSE_INDISPONIBLE: Final[Reponses] = {
    503: {
        "model": ErrorResponse,
        "description": "Base injoignable, ou extension TimescaleDB absente de la base.",
    },
}

REPONSES_AUTHENTIFIEES: Final[Reponses] = {
    401: {
        "model": ErrorResponse,
        "description": (
            "Jeton absent, illisible, périmé, ou rendu caduc par un changement de rôle ou une "
            "désactivation. L'en-tête `WWW-Authenticate` porte la cause dans `error=`."
        ),
    },
}

REPONSES_ADMIN: Final[Reponses] = {
    **REPONSES_AUTHENTIFIEES,
    403: {
        "model": ErrorResponse,
        "description": (
            "Droits insuffisants, ou mot de passe provisoire à changer quand `detail` vaut "
            "`password_change_required`."
        ),
    },
}

# `lecteur` est le rôle minimum : `require_role` n'y refuse jamais un 403 pour droits
# insuffisants, seulement pour le mot de passe provisoire.
REPONSES_LECTEUR: Final[Reponses] = {
    **REPONSES_AUTHENTIFIEES,
    403: {
        "model": ErrorResponse,
        "description": (
            "Mot de passe provisoire à changer (`detail` vaut `password_change_required`)."
        ),
    },
}

REPONSE_ORIGINE_REFUSEE: Final[Reponses] = {
    403: {
        "model": ErrorResponse,
        "description": "Origine non autorisée (protection CSRF de `require_trusted_origin`).",
    },
}

REPONSE_LIMITE: Final[Reponses] = {
    429: {
        "model": ErrorResponse,
        "description": "Trop de demandes sur cette fenêtre glissante.",
        "headers": {
            "Retry-After": {
                "description": "Secondes à attendre avant une nouvelle tentative.",
                "schema": {"type": "integer"},
            }
        },
    },
}
