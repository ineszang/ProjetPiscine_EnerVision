# Piège : `get_current_principal()` relit le compte en base à chaque requête au lieu de faire
# confiance aux claims. C'est le renoncement assumé à la propriété « sans état » : sur un seul
# service et une seule base, elle n'achetait rien, et la lecture par clé primaire coûte moins
# d'un pour cent du budget d'une requête. Ce qu'elle achète, c'est la révocation immédiate.
# Piège : le `Principal` est construit depuis la ligne, jamais depuis le claim `role`. Un claim
# périmé ne peut donc pas provoquer d'élévation de privilège.

from collections.abc import Callable
from datetime import timedelta
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.hashing import Argon2Hasher, build_hasher
from app.core.mailer import Mailer, SmtpConfig
from app.core.principal import Principal
from app.core.roles import AccountKind, Role, has_at_least
from app.core.security import TokenExpiredError, TokenInvalidError, TokenPolicy
from app.core.security import decode_access_token as decode_token
from app.db.session import get_session
from app.repositories.alert import AlertRepository
from app.repositories.audit_log import AuditLogRepository
from app.repositories.login_attempt import LoginAttemptRepository
from app.repositories.password_reset_attempt import PasswordResetAttemptRepository
from app.repositories.password_reset_token import PasswordResetTokenRepository
from app.repositories.reading import ReadingRepository
from app.repositories.recommendation import RecommendationRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.site import SiteRepository
from app.repositories.user import UserRepository
from app.services.alert import AlertService
from app.services.auth import AuthService, LoginPolicy, PasswordResetPolicy
from app.services.recommendation import RecommendationService
from app.services.sensor import SensorService
from app.services.site import SiteService
from app.services.stats import StatsService
from app.services.user import UserService

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

CODE_CHANGEMENT_REQUIS = "password_change_required"

_porteur = HTTPBearer(auto_error=False, scheme_name="Jeton d'accès")
CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(_porteur)]


def _non_authentifie(description: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentification requise",
        headers={"WWW-Authenticate": f'Bearer error="{description}"'},
    )


def get_token_policy(settings: SettingsDep) -> TokenPolicy:
    return TokenPolicy(
        secret=settings.secret_key.get_secret_value(),
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        access_ttl=timedelta(seconds=settings.access_token_ttl_seconds),
    )


# Construire un `Argon2Hasher` calcule un haché leurre, donc 17 ms : il est mis en cache sur
# les paramètres plutôt que reconstruit à chaque requête.
@lru_cache
def _hasher_cache(
    time_cost: int, memory_cost_kib: int, parallelism: int, max_concurrency: int
) -> Argon2Hasher:
    return build_hasher(
        time_cost=time_cost,
        memory_cost_kib=memory_cost_kib,
        parallelism=parallelism,
        max_concurrency=max_concurrency,
    )


def get_hasher(settings: SettingsDep) -> Argon2Hasher:
    return _hasher_cache(
        settings.argon2_time_cost,
        settings.argon2_memory_cost_kib,
        settings.argon2_parallelism,
        settings.argon2_max_concurrency,
    )


def get_client_ip(request: Request, settings: SettingsDep) -> str | None:
    # Derrière un proxy, `request.client.host` vaut l'IP du proxy : le compteur par IP
    # deviendrait global, donc un déni de service auto-infligé. Le dernier élément est le seul
    # qu'un proxy de confiance ait écrit, les précédents sont fournis par le client.
    if settings.trust_proxy_headers:
        transmis = request.headers.get("x-forwarded-for")
        if transmis:
            return transmis.split(",")[-1].strip()
    return request.client.host if request.client else None


def get_mailer(settings: SettingsDep) -> Mailer:
    return Mailer(
        SmtpConfig(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=(
                settings.smtp_password.get_secret_value() if settings.smtp_password else None
            ),
            use_tls=settings.smtp_use_tls,
            from_address=settings.smtp_from_address,
        )
    )


def get_auth_service(
    session: SessionDep,
    settings: SettingsDep,
    hasher: Annotated[Argon2Hasher, Depends(get_hasher)],
    token_policy: Annotated[TokenPolicy, Depends(get_token_policy)],
    mailer: Annotated[Mailer, Depends(get_mailer)],
) -> AuthService:
    return AuthService(
        users=UserRepository(session),
        attempts=LoginAttemptRepository(session),
        refresh_tokens=RefreshTokenRepository(session),
        audit=AuditLogRepository(session),
        hasher=hasher,
        transaction=session,
        token_policy=token_policy,
        login_policy=LoginPolicy(
            window_seconds=settings.login_window_seconds,
            max_failures_per_identifier_and_ip=(settings.login_max_failures_per_identifier_and_ip),
            max_failures_per_ip=settings.login_max_failures_per_ip,
            max_failures_per_identifier=settings.login_max_failures_per_identifier,
        ),
        refresh_ttl=timedelta(seconds=settings.refresh_token_ttl_seconds),
        reset_tokens=PasswordResetTokenRepository(session),
        reset_attempts=PasswordResetAttemptRepository(session),
        reset_policy=PasswordResetPolicy(
            window_seconds=settings.password_reset_window_seconds,
            max_requests_per_identifier=settings.password_reset_max_requests_per_identifier,
            max_requests_per_ip=settings.password_reset_max_requests_per_ip,
            token_ttl=timedelta(seconds=settings.password_reset_ttl_seconds),
            frontend_reset_url=settings.frontend_reset_password_url,
        ),
        mailer=mailer,
    )


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_user_service(
    session: SessionDep,
    hasher: Annotated[Argon2Hasher, Depends(get_hasher)],
) -> UserService:
    return UserService(
        users=UserRepository(session),
        refresh_tokens=RefreshTokenRepository(session),
        audit=AuditLogRepository(session),
        hasher=hasher,
        transaction=session,
    )


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


def get_site_service(session: SessionDep) -> SiteService:
    return SiteService(sites=SiteRepository(session))


SiteServiceDep = Annotated[SiteService, Depends(get_site_service)]


def get_alert_service(session: SessionDep) -> AlertService:
    return AlertService(alerts=AlertRepository(session))


AlertServiceDep = Annotated[AlertService, Depends(get_alert_service)]


def get_recommendation_service(session: SessionDep) -> RecommendationService:
    return RecommendationService(recommendations=RecommendationRepository(session))


RecommendationServiceDep = Annotated[RecommendationService, Depends(get_recommendation_service)]


def get_stats_service(session: SessionDep) -> StatsService:
    return StatsService(sites=SiteRepository(session), readings=ReadingRepository(session))


StatsServiceDep = Annotated[StatsService, Depends(get_stats_service)]


def get_sensor_service(session: SessionDep) -> SensorService:
    return SensorService(sites=SiteRepository(session), readings=ReadingRepository(session))


SensorServiceDep = Annotated[SensorService, Depends(get_sensor_service)]


async def get_current_principal(
    credentials: CredentialsDep,
    session: SessionDep,
    token_policy: Annotated[TokenPolicy, Depends(get_token_policy)],
) -> Principal:
    if credentials is None:
        raise _non_authentifie("invalid_request")

    try:
        claims = decode_token(token_policy, credentials.credentials)
    except TokenExpiredError as erreur:
        raise _non_authentifie("expired") from erreur
    except TokenInvalidError as erreur:
        raise _non_authentifie("invalid_token") from erreur

    compte = await UserRepository(session).get_by_id(claims.subject)
    if compte is None or not compte.is_active:
        raise _non_authentifie("invalid_token")
    # Piège : `iat` est une date JWT, donc en secondes entières. Comparer sans tronquer le
    # marqueur rejetterait tout jeton émis dans la même seconde que le changement, c'est-à-dire
    # celui que `/auth/password` vient de rendre pour garder l'appareil courant connecté.
    if int(claims.issued_at.timestamp()) < int(compte.credentials_changed_at.timestamp()):
        raise _non_authentifie("token_stale")
    if claims.role != compte.role:
        raise _non_authentifie("token_stale")

    return Principal(
        id=compte.id,
        email=compte.email,
        role=Role(compte.role),
        kind=AccountKind(compte.kind),
        must_change_password=compte.must_change_password,
    )


CurrentPrincipalDep = Annotated[Principal, Depends(get_current_principal)]


def require_role(minimum: Role) -> Callable[[Principal], Principal]:
    def garde(principal: CurrentPrincipalDep) -> Principal:
        if principal.must_change_password:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=CODE_CHANGEMENT_REQUIS
            )
        if not has_at_least(principal.role, minimum):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Droits insuffisants")
        return principal

    return garde


LecteurDep = Annotated[Principal, Depends(require_role(Role.LECTEUR))]
OperateurDep = Annotated[Principal, Depends(require_role(Role.OPERATEUR))]
AdminDep = Annotated[Principal, Depends(require_role(Role.ADMIN))]


def require_trusted_origin(request: Request, settings: SettingsDep) -> None:
    # Un navigateur envoie toujours `Origin` sur une requête non sûre. Son absence signale un
    # client hors navigateur, qui ne détient aucun cookie de victime : rien à protéger.
    origine = request.headers.get("origin")
    if origine is None:
        return
    if origine not in settings.allowed_origins:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origine refusée")
