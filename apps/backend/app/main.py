from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.requests import Request
from starlette.responses import HTMLResponse

from app.api.errors import register_error_handlers
from app.api.middleware import SecurityHeadersMiddleware
from app.api.openapi import DESCRIPTION, SUMMARY, TAGS
from app.api.security import require_metrics_token
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import get_engine

logger = get_logger(__name__)

METHODES_AUTORISEES = ["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"]
EN_TETES_AUTORISES = ["Authorization", "Content-Type"]
STATIC_DIR = Path(__file__).parent / "static"
LOGO_URL = "/static/logo-icon.png"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info(
        "Démarrage de %s %s en environnement %s", settings.name, settings.version, settings.env
    )
    yield
    await get_engine().dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved)

    documentee = resolved.api_docs_are_exposed
    application = FastAPI(
        title=resolved.name,
        version=resolved.version,
        summary=SUMMARY,
        description=DESCRIPTION,
        openapi_tags=TAGS,
        debug=resolved.debug,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json" if documentee else None,
    )

    if documentee:
        application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

        # ReDoc supporte nativement `info.x-logo` (extension Redocly) pour afficher un logo
        # en en-tête ; Swagger UI n'a pas d'equivalent, il ne reprend que le favicon.
        def openapi_avec_logo() -> dict[str, object]:
            if application.openapi_schema:
                return application.openapi_schema
            schema = get_openapi(
                title=application.title,
                version=application.version,
                summary=application.summary,
                description=application.description,
                routes=application.routes,
                tags=application.openapi_tags,
            )
            schema["info"]["x-logo"] = {"url": LOGO_URL, "altText": "EnerVision"}
            application.openapi_schema = schema
            return application.openapi_schema

        application.openapi = openapi_avec_logo  # type: ignore[method-assign]

        @application.get("/docs", include_in_schema=False)
        async def docs_swagger(_: Request) -> HTMLResponse:
            return get_swagger_ui_html(
                openapi_url="/openapi.json",
                title=f"{application.title} · Swagger UI",
                swagger_favicon_url=LOGO_URL,
            )

        @application.get("/redoc", include_in_schema=False)
        async def docs_redoc(_: Request) -> HTMLResponse:
            return get_redoc_html(
                openapi_url="/openapi.json",
                title=f"{application.title} · ReDoc",
                redoc_favicon_url=LOGO_URL,
            )

    application.add_middleware(SecurityHeadersMiddleware)

    if resolved.allowed_origins:
        # Méthodes et en-têtes listés plutôt que joker : avec `allow_credentials`, la liste
        # d'origines devient l'unique contrôle, autant documenter le contrat exact.
        application.add_middleware(
            CORSMiddleware,
            allow_origins=resolved.allowed_origins,
            allow_credentials=True,
            allow_methods=METHODES_AUTORISEES,
            allow_headers=EN_TETES_AUTORISES,
            expose_headers=["Retry-After"],
            max_age=600,
        )

    register_error_handlers(application)

    Instrumentator().instrument(application).expose(
        application,
        endpoint="/metrics",
        include_in_schema=False,
        dependencies=[Depends(require_metrics_token)],
    )
    application.include_router(api_router, prefix=resolved.api_prefix)

    # Piège : sans cette surcharge, une configuration passée à `create_app()` ne piloterait
    # que la construction, et les dépendances continueraient de lire `get_settings()` depuis
    # l'environnement. Un test « en production » ne testerait alors pas la production.
    if settings is not None:
        application.dependency_overrides[get_settings] = lambda: resolved

    return application
