# Piège : les compteurs de limitation sont lus AVANT le hachage Argon2. Dans l'autre ordre,
# chaque requête rejetée coûterait quand même 17 ms de processeur et 19 Mio de mémoire, et la
# protection deviendrait l'amplificateur de déni de service qu'elle est censée empêcher.
# Piège : quand l'email est inconnu, `verify_dummy()` consomme le même temps qu'une
# vérification réelle. Sans lui, l'écart de temps de réponse est un oracle d'existence.
# Piège : la tentative échouée est validée en base AVANT que l'erreur ne soit levée.
# `get_session()` ne valide pas de lui-même, donc la preuve disparaîtrait avec la transaction.

from dataclasses import dataclass
from typing import NoReturn, Protocol
from uuid import UUID

from app.core.hashing import Argon2Hasher
from app.core.principal import Principal
from app.core.roles import AccountKind, Role
from app.core.security import TokenPolicy, encode_access_token
from app.models.audit_log import AuditAction
from app.models.login_attempt import LoginOutcome
from app.repositories.audit_log import AuditLogRepository
from app.repositories.login_attempt import LoginAttemptRepository
from app.repositories.user import UserRepository


class Transaction(Protocol):
    async def commit(self) -> None: ...


class AuthError(Exception):
    pass


class InvalidCredentialsError(AuthError):
    pass


class RateLimitedError(AuthError):
    def __init__(self, retry_after: int) -> None:
        super().__init__("Trop de tentatives")
        self.retry_after = retry_after


@dataclass(frozen=True, slots=True)
class LoginPolicy:
    window_seconds: int
    max_failures_per_identifier_and_ip: int
    max_failures_per_ip: int
    max_failures_per_identifier: int


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    principal: Principal
    access_token: str
    expires_in: int


class AuthService:
    def __init__(
        self,
        *,
        users: UserRepository,
        attempts: LoginAttemptRepository,
        audit: AuditLogRepository,
        hasher: Argon2Hasher,
        transaction: Transaction,
        token_policy: TokenPolicy,
        login_policy: LoginPolicy,
    ) -> None:
        self._users = users
        self._attempts = attempts
        self._audit = audit
        self._hasher = hasher
        self._transaction = transaction
        self._token_policy = token_policy
        self._login_policy = login_policy

    async def authenticate(
        self, *, email: str, password: str, client_ip: str | None, user_agent: str | None
    ) -> AuthenticatedSession:
        await self._refuse_si_limite(email=email, client_ip=client_ip, user_agent=user_agent)

        compte = await self._users.get_by_email(email)
        if compte is None:
            await self._hasher.verify_dummy()
            await self._echoue(email, client_ip, LoginOutcome.IDENTIFIANTS_INVALIDES)

        if not await self._hasher.verify(compte.password_hash, password):
            await self._echoue(
                email, client_ip, LoginOutcome.IDENTIFIANTS_INVALIDES, user_id=compte.id
            )

        if not compte.is_active or compte.kind != AccountKind.HUMAIN.value:
            await self._echoue(
                email, client_ip, LoginOutcome.COMPTE_INDISPONIBLE, user_id=compte.id
            )

        if self._hasher.needs_rehash(compte.password_hash):
            await self._users.rehash_password(compte.id, await self._hasher.hash(password))

        await self._users.touch_last_login(compte.id)
        await self._attempts.record(
            email=email, client_ip=client_ip, outcome=LoginOutcome.SUCCES, user_id=compte.id
        )
        await self._transaction.commit()

        return self.issue_access_token(
            Principal(
                id=compte.id,
                email=compte.email,
                role=Role(compte.role),
                kind=AccountKind(compte.kind),
                must_change_password=compte.must_change_password,
            )
        )

    def issue_access_token(self, principal: Principal) -> AuthenticatedSession:
        jeton = encode_access_token(
            self._token_policy,
            subject=principal.id,
            role=principal.role.value,
            kind=principal.kind.value,
        )
        return AuthenticatedSession(
            principal=principal,
            access_token=jeton,
            expires_in=int(self._token_policy.access_ttl.total_seconds()),
        )

    async def _refuse_si_limite(
        self, *, email: str, client_ip: str | None, user_agent: str | None
    ) -> None:
        politique = self._login_policy
        compteurs = await self._attempts.count_recent_failures(
            email=email, client_ip=client_ip, window_seconds=politique.window_seconds
        )

        depasse = (
            compteurs.per_identifier_and_ip >= politique.max_failures_per_identifier_and_ip
            or compteurs.per_ip >= politique.max_failures_per_ip
            or compteurs.per_identifier >= politique.max_failures_per_identifier
        )
        if not depasse:
            return

        await self._attempts.record(email=email, client_ip=client_ip, outcome=LoginOutcome.LIMITE)
        # Un blocage déclenché par l'identifiant seul signe une attaque distribuée : lui seul
        # mérite une trace durable, les échecs ordinaires restent dans `login_attempt`.
        if compteurs.per_identifier >= politique.max_failures_per_identifier:
            await self._audit.record(
                action=AuditAction.LIMITE_PAR_IDENTIFIANT,
                actor_label=email.strip().lower(),
                client_ip=client_ip,
                user_agent=user_agent,
                detail={"motif": "seuil par identifiant depasse"},
            )
        await self._transaction.commit()
        raise RateLimitedError(politique.window_seconds)

    async def _echoue(
        self,
        email: str,
        client_ip: str | None,
        outcome: LoginOutcome,
        *,
        user_id: UUID | None = None,
    ) -> NoReturn:
        await self._attempts.record(
            email=email, client_ip=client_ip, outcome=outcome, user_id=user_id
        )
        await self._transaction.commit()
        raise InvalidCredentialsError("Identifiants invalides")
