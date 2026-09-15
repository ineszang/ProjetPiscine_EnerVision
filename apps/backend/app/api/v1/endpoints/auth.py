from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.deps import AuthServiceDep, CurrentPrincipalDep, get_client_ip
from app.core.logging import get_logger
from app.schemas.auth import LoginRequest, PrincipalResponse, TokenResponse
from app.services.auth import InvalidCredentialsError, RateLimitedError

router = APIRouter()
logger = get_logger(__name__)

DETAIL_IDENTIFIANTS = "Identifiants invalides"


@router.post("/login", response_model=TokenResponse, summary="Ouvre une session")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: AuthServiceDep,
    client_ip: str | None = Depends(get_client_ip),
) -> TokenResponse:
    # Une réponse d'authentification ne doit jamais être conservée par un intermédiaire.
    response.headers["Cache-Control"] = "no-store"
    agent = request.headers.get("user-agent")

    try:
        session = await service.authenticate(
            email=payload.email,
            password=payload.password,
            client_ip=client_ip,
            user_agent=agent,
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
    return TokenResponse(
        access_token=session.access_token,
        expires_in=session.expires_in,
        principal=PrincipalResponse.from_principal(session.principal),
    )


@router.get("/me", response_model=PrincipalResponse, summary="Décrit le compte connecté")
async def me(principal: CurrentPrincipalDep) -> PrincipalResponse:
    return PrincipalResponse.from_principal(principal)
