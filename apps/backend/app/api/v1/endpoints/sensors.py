from fastapi import APIRouter

from app.api.deps import AdminDep, SensorServiceDep
from app.schemas.sensor import SensorStatusResponse

router = APIRouter()


@router.get(
    "/status",
    response_model=SensorStatusResponse,
    summary="État de santé des capteurs par site",
)
async def get_status(_: AdminDep, service: SensorServiceDep) -> SensorStatusResponse:
    etat = await service.status()
    return SensorStatusResponse.model_validate(etat)
