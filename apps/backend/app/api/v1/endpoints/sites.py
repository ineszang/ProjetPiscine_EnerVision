from fastapi import APIRouter, HTTPException, status

from app.api.deps import LecteurDep, SiteServiceDep
from app.schemas.site import SiteResponse
from app.services.site import SiteNotFoundError

router = APIRouter()


@router.get("", response_model=list[SiteResponse], summary="Liste les sites")
async def list_sites(_: LecteurDep, service: SiteServiceDep) -> list[SiteResponse]:
    sites = await service.list_all()
    return [SiteResponse.model_validate(site) for site in sites]


@router.get("/{site_id}", response_model=SiteResponse, summary="Décrit un site")
async def get_site(site_id: str, _: LecteurDep, service: SiteServiceDep) -> SiteResponse:
    try:
        site = await service.get_by_id(site_id)
    except SiteNotFoundError as erreur:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Site introuvable"
        ) from erreur
    return SiteResponse.model_validate(site)
