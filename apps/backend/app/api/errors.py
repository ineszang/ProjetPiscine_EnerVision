# Piège : la réponse 422 par défaut de FastAPI contient la clé `input`, c'est-à-dire la valeur
# rejetée. Sur `/auth/login`, un corps malformé renverrait donc le mot de passe au client et le
# déposerait dans les journaux d'erreur. `validation_error_handler()` ne laisse passer que le
# champ fautif et le type d'erreur.

import uuid
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


async def validation_error_handler(_: Request, exception: RequestValidationError) -> JSONResponse:
    champs: list[dict[str, Any]] = [
        {
            "champ": ".".join(str(element) for element in erreur["loc"]),
            "type": erreur["type"],
        }
        for erreur in exception.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": champs}
    )


async def unhandled_error_handler(request: Request, exception: Exception) -> JSONResponse:
    correlation = uuid.uuid4().hex
    logger.exception(
        "erreur non gérée correlation=%s methode=%s chemin=%s",
        correlation,
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Erreur interne", "correlation": correlation},
    )


def register_error_handlers(application: FastAPI) -> None:
    application.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    application.add_exception_handler(Exception, unhandled_error_handler)
