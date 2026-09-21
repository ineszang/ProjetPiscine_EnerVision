from fastapi import APIRouter

from app.api.deps import AlertServiceDep, LecteurDep
from app.api.openapi import REPONSE_VALIDATION
from app.schemas.alert import AlertResponse, AlertSeverity

router = APIRouter()


@router.get(
    "",
    response_model=list[AlertResponse],
    summary="Liste les alertes",
    responses=REPONSE_VALIDATION,
)
async def list_alerts(
    _: LecteurDep,
    service: AlertServiceDep,
    site_id: str | None = None,
    severity: AlertSeverity | None = None,
) -> list[AlertResponse]:
    alertes = await service.list_all(site_id=site_id, severity=severity)
    return [AlertResponse.model_validate(alerte) for alerte in alertes]
