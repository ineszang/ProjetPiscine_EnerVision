# Pourquoi : `/metrics` est protégé par un jeton statique et non par un rôle applicatif. Coupler
# la supervision au modèle d'utilisateurs casserait la collecte à chaque panne
# d'authentification, c'est-à-dire précisément quand on a besoin des métriques. Le vrai contrôle
# reste le réseau : Prometheus scrute sur le réseau interne et `/metrics` ne sort pas.

import secrets

from fastapi import HTTPException, Request, status

from app.api.deps import SettingsDep


def require_metrics_token(request: Request, settings: SettingsDep) -> None:
    attendu = settings.metrics_token
    if attendu is None:
        return

    presente = request.headers.get("authorization", "")
    prefixe = "Bearer "
    if not presente.startswith(prefixe) or not secrets.compare_digest(
        presente[len(prefixe) :], attendu.get_secret_value()
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Jeton requis")
