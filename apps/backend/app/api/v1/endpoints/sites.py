from fastapi import APIRouter, HTTPException, status

from app.api.deps import LecteurDep, ReadingServiceDep, SiteServiceDep
from app.api.openapi import REPONSE_VALIDATION, Reponses
from app.schemas.errors import ErrorResponse
from app.schemas.reading import ReadingResponse
from app.schemas.site import SiteResponse
from app.services.site import SiteNotFoundError

router = APIRouter()

REPONSES_INTROUVABLE: Reponses = {
    **REPONSE_VALIDATION,
    404: {"model": ErrorResponse, "description": "Aucun site ne porte cet identifiant."},
}


@router.get("", response_model=list[SiteResponse], summary="Liste les sites")
async def list_sites(_: LecteurDep, service: SiteServiceDep) -> list[SiteResponse]:
    sites = await service.list_all()
    return [SiteResponse.model_validate(site) for site in sites]


@router.get(
    "/{site_id}",
    response_model=SiteResponse,
    summary="Décrit un site",
    responses=REPONSES_INTROUVABLE,
)
async def get_site(site_id: str, _: LecteurDep, service: SiteServiceDep) -> SiteResponse:
    try:
        site = await service.get_by_id(site_id)
    except SiteNotFoundError as erreur:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Site introuvable"
        ) from erreur
    return SiteResponse.model_validate(site)


@router.get(
    "/{site_id}/current",
    response_model=ReadingResponse | None,
    summary="Dernière mesure connue d'un site",
    responses=REPONSES_INTROUVABLE,
)
async def get_current(
    site_id: str, _: LecteurDep, sites: SiteServiceDep, readings: ReadingServiceDep
) -> ReadingResponse | None:
    try:
        await sites.get_by_id(site_id)
    except SiteNotFoundError as erreur:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Site introuvable"
        ) from erreur
    derniere = await readings.get_latest(site_id)
    return ReadingResponse.model_validate(derniere) if derniere is not None else None
