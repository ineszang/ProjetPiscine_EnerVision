from fastapi import APIRouter

from app.api.deps import LecteurDep, StatsServiceDep
from app.schemas.stats import StatsSummaryResponse

router = APIRouter()


@router.get(
    "/summary",
    response_model=StatsSummaryResponse,
    summary="Résume la consommation instantanée du parc",
)
async def get_summary(_: LecteurDep, service: StatsServiceDep) -> StatsSummaryResponse:
    resume = await service.summary()
    return StatsSummaryResponse.model_validate(resume)
