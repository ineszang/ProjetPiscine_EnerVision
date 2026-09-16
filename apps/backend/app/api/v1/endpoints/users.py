from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import AdminDep, UserServiceDep
from app.api.openapi import REPONSE_VALIDATION, Reponses
from app.core.logging import get_logger
from app.schemas.errors import ErrorResponse
from app.schemas.user import (
    TemporaryPasswordResponse,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from app.services.user import EmailAlreadyUsedError, LastAdminError, UserNotFoundError

router = APIRouter()
logger = get_logger(__name__)

REPONSES_CREATION: Reponses = {
    **REPONSE_VALIDATION,
    409: {"model": ErrorResponse, "description": "Adresse déjà portée par un autre compte."},
}

REPONSES_INTROUVABLE: Reponses = {
    **REPONSE_VALIDATION,
    404: {"model": ErrorResponse, "description": "Aucun compte ne porte cet identifiant."},
}

REPONSES_MODIFICATION: Reponses = {
    **REPONSES_INTROUVABLE,
    400: {"model": ErrorResponse, "description": "Corps vide, aucune modification demandée."},
    409: {
        "model": ErrorResponse,
        "description": (
            "L'opération laisserait la plateforme sans administrateur actif, qu'il s'agisse de "
            "rétrograder le dernier ou de le désactiver."
        ),
    },
}


@router.get("", response_model=list[UserResponse], summary="Liste les comptes")
async def list_users(_: AdminDep, service: UserServiceDep) -> list[UserResponse]:
    comptes = await service.list_all()
    return [UserResponse.model_validate(compte) for compte in comptes]


@router.post(
    "",
    response_model=TemporaryPasswordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crée un compte avec un mot de passe provisoire",
    responses=REPONSES_CREATION,
)
async def create_user(
    payload: UserCreateRequest,
    acteur: AdminDep,
    service: UserServiceDep,
    response: Response,
) -> TemporaryPasswordResponse:
    # Le mot de passe provisoire ne doit être conservé par aucun intermédiaire.
    response.headers["Cache-Control"] = "no-store"
    try:
        cree = await service.create(
            actor=acteur,
            email=payload.email,
            role=payload.role,
            full_name=payload.full_name,
        )
    except EmailAlreadyUsedError as erreur:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Adresse déjà utilisée"
        ) from erreur

    logger.info("user.created actor=%s target=%s", acteur.id, cree.user.id)
    return TemporaryPasswordResponse(
        user=UserResponse.model_validate(cree.user),
        temporary_password=cree.temporary_password,
    )


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Change le rôle ou l'activation",
    responses=REPONSES_MODIFICATION,
)
async def update_user(
    user_id: UUID,
    payload: UserUpdateRequest,
    acteur: AdminDep,
    service: UserServiceDep,
) -> UserResponse:
    compte = None
    try:
        if payload.role is not None:
            compte = await service.change_role(actor=acteur, user_id=user_id, role=payload.role)
        if payload.is_active is not None:
            compte = await service.set_active(
                actor=acteur, user_id=user_id, is_active=payload.is_active
            )
    except UserNotFoundError as erreur:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Compte introuvable"
        ) from erreur
    except LastAdminError as erreur:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dernier administrateur actif, l'opération le laisserait sans successeur",
        ) from erreur

    if compte is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Aucune modification demandée"
        )
    logger.info("user.updated actor=%s target=%s", acteur.id, user_id)
    return UserResponse.model_validate(compte)


@router.post(
    "/{user_id}/password-reset",
    response_model=TemporaryPasswordResponse,
    summary="Réinitialise le mot de passe et ferme les sessions",
    responses=REPONSES_INTROUVABLE,
)
async def reset_password(
    user_id: UUID, acteur: AdminDep, service: UserServiceDep, response: Response
) -> TemporaryPasswordResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        reinitialise = await service.reset_password(actor=acteur, user_id=user_id)
    except UserNotFoundError as erreur:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Compte introuvable"
        ) from erreur

    logger.info("user.password_reset actor=%s target=%s", acteur.id, user_id)
    return TemporaryPasswordResponse(
        user=UserResponse.model_validate(reinitialise.user),
        temporary_password=reinitialise.temporary_password,
    )
