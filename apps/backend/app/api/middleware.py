# Pourquoi : `SecurityHeadersMiddleware` ne pose ni HSTS ni CSP, et c'est délibéré.
# L'application ignore si TLS termine devant elle, donc elle ne peut pas décider d'un HSTS ;
# et une CSP sur une API JSON ne protège presque rien, celle qui compte protège la page
# Angular. Les deux appartiennent au terminateur TLS.
# Contrainte : `/docs` charge Swagger depuis un CDN, une CSP stricte ici casserait la
# documentation sans rien sécuriser.

from collections.abc import Awaitable, Callable
from typing import Final

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

EN_TETES: Final[dict[str, str]] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    # same-origin : aucun client ne charge l'API en no-cors depuis une autre origine
    # (proxy.conf.json en dev, reverse proxy nginx ensuite, cf. docs/architecture/20-backend.md).
    "Cross-Origin-Resource-Policy": "same-origin",
}

PREFIXE_AUTHENTIFICATION: Final = "/auth"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        for nom, valeur in EN_TETES.items():
            response.headers.setdefault(nom, valeur)

        # Une réponse d'authentification ne doit jamais être conservée par un intermédiaire.
        if PREFIXE_AUTHENTIFICATION in request.url.path:
            response.headers["Cache-Control"] = "no-store"
        return response
