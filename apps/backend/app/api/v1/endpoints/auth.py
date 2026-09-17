# Piège : le jeton de rafraîchissement ne quitte jamais le cookie httpOnly, et le jeton
# d'accès ne va jamais dans un cookie. C'est ce qui réduit la surface CSRF aux trois routes de
# ce module : partout ailleurs, le navigateur n'attache rien de lui-même.

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status

from app.api.deps import (
    AuthServiceDep,
    CurrentPrincipalDep,
    SettingsDep,
    get_client_ip,
    require_trusted_origin,
)
from app.api.openapi import (
    REPONSE_LIMITE,
    REPONSE_ORIGINE_REFUSEE,
    REPONSE_VALIDATION,
    REPONSES_AUTHENTIFIEES,
    Reponses,
    cookie_de_rafraichissement,
)
from app.core.cookies import RefreshCookie, cookie_name
from app.core.logging import get_logger
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    PasswordChangeRequest,
    PrincipalResponse,
    ResetPasswordRequest,
    TokenResponse,
)
from app.schemas.errors import ErrorResponse
from app.services.auth import (
    AuthenticatedSession,
    InvalidCredentialsError,
    InvalidOrExpiredResetTokenError,
    RateLimitedError,
    SessionRejectedError,
)

router = APIRouter()
logger = get_logger(__name__)

DETAIL_IDENTIFIANTS = "Identifiants invalides"
DETAIL_SESSION = "Session invalide"
DETAIL_LIEN_RESET = "Lien invalide ou expiré"

REPONSES_LOGIN: Reponses = {
    **REPONSE_VALIDATION,
    401: {
        "model": ErrorResponse,
        "description": (
            "Identifiants faux, compte inconnu ou compte désactivé. Le message est le même dans "
            "les trois cas, et n'apprend donc rien sur l'existence du compte."
        ),
    },
    429: {
        "model": ErrorResponse,
        "description": "Trop de tentatives sur cette fenêtre glissante.",
        "headers": {
            "Retry-After": {
                "description": "Secondes à attendre avant une nouvelle tentative.",
                "schema": {"type": "integer"},
            }
        },
    },
}

REPONSES_REFRESH: Reponses = {
    **REPONSE_ORIGINE_REFUSEE,
    401: {
        "model": ErrorResponse,
        "description": (
            "Cookie absent, session expirée, révoquée, ou jeton déjà tourné. Dans ce dernier cas "
            "toute la famille de sessions est révoquée et le cookie est effacé avec la réponse."
        ),
    },
}

REPONSES_LOGOUT: Reponses = {**REPONSE_ORIGINE_REFUSEE}

REPONSES_LOGOUT_ALL: Reponses = {**REPONSES_AUTHENTIFIEES, **REPONSE_ORIGINE_REFUSEE}

REPONSES_MOT_DE_PASSE: Reponses = {
    **REPONSE_VALIDATION,
    **REPONSE_ORIGINE_REFUSEE,
    401: {
        "model": ErrorResponse,
        "description": "Jeton d'accès invalide, ou mot de passe courant faux.",
    },
}

REPONSES_FORGOT_PASSWORD: Reponses = {
    **REPONSE_VALIDATION,
    **REPONSE_LIMITE,
}

REPONSES_RESET_PASSWORD: Reponses = {
    **REPONSE_VALIDATION,
    **REPONSE_ORIGINE_REFUSEE,
    400: {
        "model": ErrorResponse,
        "description": "Lien invalide, déjà utilisé, ou expiré (durée de vie : 15 minutes).",
    },
}


def repond(
    response: Response, settings: SettingsDep, session: AuthenticatedSession
) -> TokenResponse:
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(**RefreshCookie.build(settings, session.refresh_secret).as_kwargs())
    return TokenResponse(
        access_token=session.access_token,
        expires_in=session.expires_in,
        principal=PrincipalResponse.from_principal(session.principal),
    )


# Piège : une `HTTPException` construit sa propre réponse, donc tout en-tête posé sur la
# `Response` injectée est perdu. L'effacement du cookie doit voyager avec l'exception,
# sans quoi un navigateur garderait un cookie mort après une détection de réutilisation.
def entete_de_suppression(settings: SettingsDep) -> str:
    temoin = Response()
    temoin.delete_cookie(**RefreshCookie.expired(settings).as_deletion_kwargs())
    return temoin.headers["set-cookie"]


def lit_le_cookie(request: Request, settings: SettingsDep) -> str:
    secret = request.cookies.get(cookie_name(settings))
    if not secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=DETAIL_SESSION)
    return secret


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Ouvre une session",
    responses=REPONSES_LOGIN,
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    settings: SettingsDep,
    service: AuthServiceDep,
    client_ip: str | None = Depends(get_client_ip),
) -> TokenResponse:
    response.headers["Cache-Control"] = "no-store"
    agent = request.headers.get("user-agent")

    try:
        session = await service.authenticate(
            email=payload.email, password=payload.password, client_ip=client_ip, user_agent=agent
        )
    except RateLimitedError as erreur:
        logger.warning("auth.rate_limited email=%s ip=%s", payload.email, client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives, réessayez plus tard",
            headers={"Retry-After": str(erreur.retry_after)},
        ) from erreur
    except InvalidCredentialsError as erreur:
        logger.warning("auth.login.failure email=%s ip=%s", payload.email, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=DETAIL_IDENTIFIANTS
        ) from erreur

    logger.info("auth.login.success user_id=%s ip=%s", session.principal.id, client_ip)
    return repond(response, settings, session)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Fait tourner la session",
    dependencies=[Depends(require_trusted_origin), Depends(cookie_de_rafraichissement)],
    responses=REPONSES_REFRESH,
)
async def refresh(
    request: Request,
    response: Response,
    settings: SettingsDep,
    service: AuthServiceDep,
    client_ip: str | None = Depends(get_client_ip),
) -> TokenResponse:
    response.headers["Cache-Control"] = "no-store"

    try:
        session = await service.refresh(
            secret=lit_le_cookie(request, settings),
            client_ip=client_ip,
            user_agent=request.headers.get("user-agent"),
        )
    except SessionRejectedError as erreur:
        logger.warning("auth.refresh.rejected ip=%s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=DETAIL_SESSION,
            headers={
                "Set-Cookie": entete_de_suppression(settings),
                "Cache-Control": "no-store",
            },
        ) from erreur

    return repond(response, settings, session)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Ferme la session courante",
    dependencies=[Depends(require_trusted_origin), Depends(cookie_de_rafraichissement)],
    responses=REPONSES_LOGOUT,
)
async def logout(
    request: Request, response: Response, settings: SettingsDep, service: AuthServiceDep
) -> None:
    response.headers["Cache-Control"] = "no-store"
    secret = request.cookies.get(cookie_name(settings))
    if secret:
        await service.logout(secret=secret)
    response.delete_cookie(**RefreshCookie.expired(settings).as_deletion_kwargs())


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Ferme toutes les sessions du compte",
    dependencies=[Depends(require_trusted_origin)],
    responses=REPONSES_LOGOUT_ALL,
)
async def logout_all(
    principal: CurrentPrincipalDep,
    response: Response,
    settings: SettingsDep,
    service: AuthServiceDep,
) -> None:
    response.headers["Cache-Control"] = "no-store"
    revoquees = await service.logout_all(principal)
    logger.info("auth.logout_all user_id=%s sessions=%s", principal.id, revoquees)
    response.delete_cookie(**RefreshCookie.expired(settings).as_deletion_kwargs())


@router.get(
    "/me",
    response_model=PrincipalResponse,
    summary="Décrit le compte connecté",
    responses=REPONSES_AUTHENTIFIEES,
)
async def me(principal: CurrentPrincipalDep) -> PrincipalResponse:
    return PrincipalResponse.from_principal(principal)


@router.post(
    "/password",
    response_model=TokenResponse,
    summary="Change son propre mot de passe",
    dependencies=[Depends(require_trusted_origin)],
    responses=REPONSES_MOT_DE_PASSE,
)
async def change_password(
    payload: PasswordChangeRequest,
    principal: CurrentPrincipalDep,
    request: Request,
    response: Response,
    settings: SettingsDep,
    service: AuthServiceDep,
    client_ip: str | None = Depends(get_client_ip),
) -> TokenResponse:
    response.headers["Cache-Control"] = "no-store"

    try:
        session = await service.change_password(
            principal=principal,
            current_password=payload.current_password,
            new_password=payload.new_password,
            client_ip=client_ip,
            user_agent=request.headers.get("user-agent"),
        )
    except InvalidCredentialsError as erreur:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=DETAIL_IDENTIFIANTS
        ) from erreur

    logger.info("auth.password_changed user_id=%s", principal.id)
    return repond(response, settings, session)


@router.post(
    "/forgot-password",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Demande un lien de réinitialisation par email",
    responses=REPONSES_FORGOT_PASSWORD,
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    response: Response,
    service: AuthServiceDep,
    background_tasks: BackgroundTasks,
    client_ip: str | None = Depends(get_client_ip),
) -> None:
    response.headers["Cache-Control"] = "no-store"

    try:
        await service.request_password_reset(
            email=payload.email,
            client_ip=client_ip,
            user_agent=request.headers.get("user-agent"),
            background_tasks=background_tasks,
        )
    except RateLimitedError as erreur:
        logger.warning("auth.password_reset.rate_limited ip=%s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de demandes, réessayez plus tard",
            headers={"Retry-After": str(erreur.retry_after)},
        ) from erreur


@router.post(
    "/reset-password",
    response_model=TokenResponse,
    summary="Choisit un nouveau mot de passe depuis un lien reçu par email",
    dependencies=[Depends(require_trusted_origin)],
    responses=REPONSES_RESET_PASSWORD,
)
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    response: Response,
    settings: SettingsDep,
    service: AuthServiceDep,
    client_ip: str | None = Depends(get_client_ip),
) -> TokenResponse:
    response.headers["Cache-Control"] = "no-store"

    try:
        session = await service.confirm_password_reset(
            token=payload.token,
            new_password=payload.new_password,
            client_ip=client_ip,
            user_agent=request.headers.get("user-agent"),
        )
    except InvalidOrExpiredResetTokenError as erreur:
        logger.warning("auth.password_reset.invalid_token ip=%s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=DETAIL_LIEN_RESET
        ) from erreur

    logger.info("auth.password_reset.success user_id=%s", session.principal.id)
    return repond(response, settings, session)
