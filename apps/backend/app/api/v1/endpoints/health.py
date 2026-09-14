from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import SessionDep, SettingsDep
from app.core.logging import get_logger
from app.schemas.health import LivenessStatus, ReadinessStatus

logger = get_logger(__name__)
router = APIRouter(tags=["health"])


@router.get("/live", summary="Sonde de vivacite")
async def liveness(settings: SettingsDep) -> LivenessStatus:
    return LivenessStatus(
        status="ok",
        service=settings.name,
        version=settings.version,
        environment=settings.env,
    )


@router.get("/ready", summary="Sonde de disponibilite")
async def readiness(session: SessionDep) -> ReadinessStatus:
    try:
        await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        logger.exception("Base de donnees injoignable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de donnees injoignable",
        ) from None
    return ReadinessStatus(status="ready", database="reachable")
