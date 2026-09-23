from fastapi import APIRouter

from app.api.deps import DriftServiceDep, OperateurDep
from app.api.openapi import REPONSE_VALIDATION
from app.schemas.drift import DriftReportResponse

router = APIRouter()


@router.get(
    "/drift",
    response_model=list[DriftReportResponse],
    summary="Dernier rapport de dérive par site, plus la ligne globale",
    responses=REPONSE_VALIDATION,
)
async def get_drift(
    _: OperateurDep, service: DriftServiceDep, site_id: str | None = None
) -> list[DriftReportResponse]:
    rapports = await service.derniers(site_id=site_id)
    return [DriftReportResponse.model_validate(rapport) for rapport in rapports]
