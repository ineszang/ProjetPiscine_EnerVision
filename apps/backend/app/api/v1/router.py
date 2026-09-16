from fastapi import APIRouter

from app.api.openapi import REPONSE_SERVEUR, REPONSES_ADMIN, REPONSES_LECTEUR
from app.api.v1.endpoints import alerts, auth, health, recommendations, sites, stats, users

api_router = APIRouter(responses=REPONSE_SERVEUR)
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"], responses=REPONSES_ADMIN)
api_router.include_router(sites.router, prefix="/sites", tags=["sites"], responses=REPONSES_LECTEUR)
api_router.include_router(
    alerts.router, prefix="/alerts", tags=["alerts"], responses=REPONSES_LECTEUR
)
api_router.include_router(
    recommendations.router,
    prefix="/recommendations",
    tags=["recommendations"],
    responses=REPONSES_LECTEUR,
)
api_router.include_router(stats.router, prefix="/stats", tags=["stats"], responses=REPONSES_LECTEUR)
