from fastapi import APIRouter

from app.api.deps import LecteurDep, PredictionServiceDep
from app.schemas.prediction import PredictionSummaryResponse

router = APIRouter()


@router.get(
    "",
    response_model=PredictionSummaryResponse,
    summary="Dernière prédiction de consommation par site",
)
async def get_predictions(
    _: LecteurDep, service: PredictionServiceDep
) -> PredictionSummaryResponse:
    resume = await service.summary()
    return PredictionSummaryResponse.model_validate(resume)
