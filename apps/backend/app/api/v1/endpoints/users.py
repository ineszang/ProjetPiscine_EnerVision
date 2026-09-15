from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import AdminDep, UserServiceDep
from app.core.logging import get_logger
from app.schemas.user import (
    TemporaryPasswordResponse,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from app.services.user import EmailAlreadyUsedError, LastAdminError, UserNotFoundError

router = APIRouter()
logger = get_logger(__name__)


@router.get("", response_model=list[UserResponse], summary="Liste les comptes")
async def list_users(_: AdminDep, service: UserServiceDep) -> list[UserResponse]:
    comptes = await service.list_all()
    return [UserResponse.model_validate(compte) for compte in comptes]


@router.post(
    "",
    response_model=TemporaryPasswordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crée un compte avec un mot de passe provisoire",
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


@router.patch("/{user_id}", response_model=UserResponse, summary="Change le rôle ou l'activation")
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
