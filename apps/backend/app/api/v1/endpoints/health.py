from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import SessionDep, SettingsDep
from app.api.openapi import REPONSE_INDISPONIBLE
from app.core.logging import get_logger
from app.schemas.health import LivenessStatus, ReadinessStatus

logger = get_logger(__name__)
router = APIRouter()

TIMESCALEDB_VERSION = text("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")


@router.get("/live", summary="Sonde de vivacité")
async def liveness(settings: SettingsDep) -> LivenessStatus:
    return LivenessStatus(
        status="ok",
        service=settings.name,
        version=settings.version,
        environment=settings.env,
    )


@router.get("/ready", summary="Sonde de disponibilité", responses=REPONSE_INDISPONIBLE)
async def readiness(session: SessionDep) -> ReadinessStatus:
    try:
        version: str | None = await session.scalar(TIMESCALEDB_VERSION)
    except SQLAlchemyError, OSError:
        logger.exception("Base de données injoignable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de données injoignable",
        ) from None

    if version is None:
        logger.error("Extension TimescaleDB absente de la base")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Extension TimescaleDB absente",
        )

    logger.debug("Extension TimescaleDB en version %s", version)
    return ReadinessStatus(status="ready", database="reachable", timescaledb="loaded")
