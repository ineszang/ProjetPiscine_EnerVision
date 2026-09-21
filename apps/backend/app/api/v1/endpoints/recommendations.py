from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminDep, LecteurDep, RecommendationServiceDep
from app.api.openapi import REPONSE_VALIDATION, REPONSES_ADMIN, Reponses
from app.schemas.errors import ErrorResponse
from app.schemas.recommendation import (
    RecommendationGenerationResponse,
    RecommendationResponse,
)
from app.services.recommendation import RecommendationNotFoundError

router = APIRouter()

REPONSES_GENERATION: Reponses = {**REPONSES_ADMIN, **REPONSE_VALIDATION}

REPONSES_INTROUVABLE: Reponses = {
    **REPONSE_VALIDATION,
    404: {"model": ErrorResponse, "description": "Aucune recommandation ne porte cet identifiant."},
}


@router.get("", response_model=list[RecommendationResponse], summary="Liste les recommandations")
async def list_recommendations(
    _: LecteurDep, service: RecommendationServiceDep
) -> list[RecommendationResponse]:
    recommendations = await service.list_all()
    return [RecommendationResponse.model_validate(r) for r in recommendations]


@router.get(
    "/{recommendation_id}",
    response_model=RecommendationResponse,
    summary="Décrit une recommandation",
    responses=REPONSES_INTROUVABLE,
)
async def get_recommendation(
    recommendation_id: int, _: LecteurDep, service: RecommendationServiceDep
) -> RecommendationResponse:
    try:
        recommendation = await service.get_by_id(recommendation_id)
    except RecommendationNotFoundError as erreur:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recommandation introuvable"
        ) from erreur
    return RecommendationResponse.model_validate(recommendation)


@router.post(
    "/generate",
    response_model=RecommendationGenerationResponse,
    summary="Génère les recommandations à partir des alertes",
    responses=REPONSES_GENERATION,
)
async def generate_recommendations(
    _: AdminDep,
    service: RecommendationServiceDep,
    site_id: str | None = None,
) -> RecommendationGenerationResponse:
    rapport = await service.generate(site_id=site_id)
    return RecommendationGenerationResponse(
        alerts_examined=rapport.alertes_examinees,
        recommendations_created=rapport.recommandations_creees,
        already_present=rapport.deja_presentes,
    )
