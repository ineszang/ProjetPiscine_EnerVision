from fastapi import APIRouter

from app.api.openapi import REPONSE_SERVEUR, REPONSES_ADMIN
from app.api.v1.endpoints import auth, health, users

api_router = APIRouter(responses=REPONSE_SERVEUR)
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"], responses=REPONSES_ADMIN)
