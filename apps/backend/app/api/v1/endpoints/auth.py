# Piège : le jeton de rafraîchissement ne quitte jamais le cookie httpOnly, et le jeton
# d'accès ne va jamais dans un cookie. C'est ce qui réduit la surface CSRF aux trois routes de
# ce module : partout ailleurs, le navigateur n'attache rien de lui-même.

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.deps import (
    AuthServiceDep,
    CurrentPrincipalDep,
    SettingsDep,
    get_client_ip,
    require_trusted_origin,
)
from app.core.cookies import RefreshCookie, cookie_name
from app.core.logging import get_logger
from app.schemas.auth import LoginRequest, PrincipalResponse, TokenResponse
from app.services.auth import (
    AuthenticatedSession,
    InvalidCredentialsError,
    RateLimitedError,
    SessionRejectedError,
)

router = APIRouter()
logger = get_logger(__name__)

DETAIL_IDENTIFIANTS = "Identifiants invalides"
DETAIL_SESSION = "Session invalide"


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


@router.post("/login", response_model=TokenResponse, summary="Ouvre une session")
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
    dependencies=[Depends(require_trusted_origin)],
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
    dependencies=[Depends(require_trusted_origin)],
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


@router.get("/me", response_model=PrincipalResponse, summary="Décrit le compte connecté")
async def me(principal: CurrentPrincipalDep) -> PrincipalResponse:
    return PrincipalResponse.from_principal(principal)
