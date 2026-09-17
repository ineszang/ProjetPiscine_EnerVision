from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import LecteurDep, ReadingServiceDep
from app.api.openapi import REPONSE_VALIDATION, Reponses
from app.schemas.errors import ErrorResponse
from app.schemas.reading import ReadingResponse
from app.services.reading import FenetreInverseeError, FenetreTropLargeError

router = APIRouter()

REPONSES_FENETRE: Reponses = {
    **REPONSE_VALIDATION,
    400: {
        "model": ErrorResponse,
        "description": (
            "Fenêtre temporelle invalide : `start` postérieur ou égal à `end`, ou écart entre "
            "les deux supérieur à 90 jours."
        ),
    },
}


@router.get(
    "",
    response_model=list[ReadingResponse],
    summary="Liste l'historique des lectures",
    responses=REPONSES_FENETRE,
)
async def list_readings(
    _: LecteurDep,
    service: ReadingServiceDep,
    site_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> list[ReadingResponse]:
    try:
        lectures = await service.list_history(
            site_id=site_id, start=start, end=end, limit=limit, offset=offset
        )
    except FenetreInverseeError as erreur:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="`start` doit être strictement antérieur à `end`",
        ) from erreur
    except FenetreTropLargeError as erreur:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'écart entre `start` et `end` ne peut pas dépasser 90 jours",
        ) from erreur
    return [ReadingResponse.model_validate(lecture) for lecture in lectures]
