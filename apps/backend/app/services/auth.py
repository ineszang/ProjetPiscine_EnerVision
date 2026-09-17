# Piège : les compteurs de limitation sont lus AVANT le hachage Argon2. Dans l'autre ordre,
# chaque requête rejetée coûterait quand même 17 ms de processeur et 19 Mio de mémoire, et la
# protection deviendrait l'amplificateur de déni de service qu'elle est censée empêcher.
# Piège : quand l'email est inconnu, `verify_dummy()` consomme le même temps qu'une
# vérification réelle. Sans lui, l'écart de temps de réponse est un oracle d'existence.
# Piège : la tentative échouée est validée en base AVANT que l'erreur ne soit levée.
# `get_session()` ne valide pas de lui-même, donc la preuve disparaîtrait avec la transaction.
# Piège : dans `refresh()`, un jeton expiré ne révoque PAS la famille, un jeton déjà tourné si.
# La rotation ne protège de rien par elle-même : elle rend la réutilisation détectable, et
# c'est la détection qui termine le vol.

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import NoReturn, Protocol
from uuid import UUID, uuid4

from fastapi import BackgroundTasks

from app.core.hashing import Argon2Hasher
from app.core.logging import get_logger
from app.core.mailer import Mailer
from app.core.principal import Principal
from app.core.roles import AccountKind, Role
from app.core.security import (
    TokenPolicy,
    encode_access_token,
    fingerprint_refresh,
    generate_refresh_secret,
)
from app.models.audit_log import AuditAction, AuditOutcome
from app.models.login_attempt import LoginOutcome
from app.models.refresh_token import RevocationReason
from app.repositories.audit_log import AuditLogRepository
from app.repositories.login_attempt import LoginAttemptRepository
from app.repositories.password_reset_attempt import PasswordResetAttemptRepository
from app.repositories.password_reset_token import PasswordResetTokenRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository

logger = get_logger(__name__)


class Transaction(Protocol):
    async def commit(self) -> None: ...


class AuthError(Exception):
    pass


class InvalidCredentialsError(AuthError):
    pass


class SessionRejectedError(AuthError):
    pass


class RateLimitedError(AuthError):
    def __init__(self, retry_after: int) -> None:
        super().__init__("Trop de tentatives")
        self.retry_after = retry_after


class InvalidOrExpiredResetTokenError(AuthError):
    pass


@dataclass(frozen=True, slots=True)
class LoginPolicy:
    window_seconds: int
    max_failures_per_identifier_and_ip: int
    max_failures_per_ip: int
    max_failures_per_identifier: int


@dataclass(frozen=True, slots=True)
class PasswordResetPolicy:
    window_seconds: int
    max_requests_per_identifier: int
    max_requests_per_ip: int
    token_ttl: timedelta
    frontend_reset_url: str


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    principal: Principal
    access_token: str
    expires_in: int
    refresh_secret: str


class AuthService:
    def __init__(
        self,
        *,
        users: UserRepository,
        attempts: LoginAttemptRepository,
        refresh_tokens: RefreshTokenRepository,
        audit: AuditLogRepository,
        hasher: Argon2Hasher,
        transaction: Transaction,
        token_policy: TokenPolicy,
        login_policy: LoginPolicy,
        refresh_ttl: timedelta,
        reset_tokens: PasswordResetTokenRepository,
        reset_attempts: PasswordResetAttemptRepository,
        reset_policy: PasswordResetPolicy,
        mailer: Mailer,
    ) -> None:
        self._users = users
        self._attempts = attempts
        self._refresh = refresh_tokens
        self._audit = audit
        self._hasher = hasher
        self._transaction = transaction
        self._token_policy = token_policy
        self._login_policy = login_policy
        self._refresh_ttl = refresh_ttl
        self._reset_tokens = reset_tokens
        self._reset_attempts = reset_attempts
        self._reset_policy = reset_policy
        self._mailer = mailer

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
        secret = await self._ouvre_une_famille(
            user_id=compte.id, client_ip=client_ip, user_agent=user_agent
        )
        await self._transaction.commit()

        return self._session(self._en_principal(compte), secret)

    async def refresh(
        self, *, secret: str, client_ip: str | None, user_agent: str | None
    ) -> AuthenticatedSession:
        empreinte = fingerprint_refresh(secret)
        revendique = await self._refresh.claim_for_rotation(empreinte)
        if revendique is None:
            await self._traite_rotation_refusee(empreinte, client_ip, user_agent)

        compte = await self._users.get_by_id(revendique.user_id)
        if compte is None or not compte.is_active:
            await self._refresh.revoke_family(revendique.family_id, RevocationReason.ADMINISTRATION)
            await self._transaction.commit()
            raise SessionRejectedError("Session révoquée")

        nouveau_secret = generate_refresh_secret()
        nouveau = await self._refresh.create(
            user_id=revendique.user_id,
            family_id=revendique.family_id,
            token_hash=fingerprint_refresh(nouveau_secret),
            expires_at=revendique.expires_at,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        await self._refresh.link_replacement(revendique.id, nouveau.id)
        await self._transaction.commit()

        return self._session(self._en_principal(compte), nouveau_secret)

    async def logout(self, *, secret: str) -> None:
        ligne = await self._refresh.inspect(fingerprint_refresh(secret))
        if ligne is not None:
            await self._refresh.revoke_family(ligne.family_id, RevocationReason.DECONNEXION)
        await self._transaction.commit()

    async def change_password(
        self,
        *,
        principal: Principal,
        current_password: str,
        new_password: str,
        client_ip: str | None,
        user_agent: str | None,
    ) -> AuthenticatedSession:
        compte = await self._users.get_by_id(principal.id)
        if compte is None or not await self._hasher.verify(compte.password_hash, current_password):
            raise InvalidCredentialsError("Identifiants invalides")

        await self._users.update_password(
            principal.id, await self._hasher.hash(new_password), must_change_password=False
        )
        # Toutes les sessions tombent, puis on en rouvre une : l'appareil courant reste
        # connecté et tous les autres sont déconnectés.
        revoquees = await self._refresh.revoke_all_for_user(
            principal.id, RevocationReason.CHANGEMENT_MOT_DE_PASSE
        )
        secret = await self._ouvre_une_famille(
            user_id=principal.id, client_ip=client_ip, user_agent=user_agent
        )
        await self._audit.record(
            action=AuditAction.COMPTE_MOT_DE_PASSE_CHANGE,
            actor=principal,
            target_type="app_user",
            target_id=str(principal.id),
            client_ip=client_ip,
            user_agent=user_agent,
            detail={"sessions_revoquees": revoquees},
        )
        await self._transaction.commit()

        rafraichi = await self._users.get_by_id(principal.id)
        return self._session(self._en_principal(rafraichi or compte), secret)

    async def request_password_reset(
        self,
        *,
        email: str,
        client_ip: str | None,
        user_agent: str | None,
        background_tasks: BackgroundTasks,
    ) -> None:
        await self._refuse_si_limite_reset(email=email, client_ip=client_ip)

        compte = await self._users.get_by_email(email)
        # Piège : le hachage factice équilibre le temps de réponse sur un compte inconnu, comme
        # `authenticate()`. La réponse et sa forme restent identiques dans tous les cas : compte
        # inconnu, compte inactif, ou email envoyé avec succès. L'envoi SMTP lui-même est différé
        # en tâche de fond : le laisser dans le chemin de réponse rouvrirait le même oracle par le
        # temps (aller-retour réseau) et par la forme (500 si le relais SMTP échoue, contre 202).
        if compte is None or not compte.is_active or compte.kind != AccountKind.HUMAIN.value:
            await self._hasher.verify_dummy()
            await self._reset_attempts.record(email=email, client_ip=client_ip)
            await self._transaction.commit()
            return

        await self._reset_tokens.invalidate_all_for_user(compte.id)
        secret = generate_refresh_secret()
        await self._reset_tokens.create(
            user_id=compte.id,
            token_hash=fingerprint_refresh(secret),
            expires_at=datetime.now(UTC) + self._reset_policy.token_ttl,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        await self._reset_attempts.record(email=email, client_ip=client_ip)
        await self._audit.record(
            action=AuditAction.MOT_DE_PASSE_OUBLIE_DEMANDE,
            actor_label=compte.email,
            target_type="app_user",
            target_id=str(compte.id),
            client_ip=client_ip,
            user_agent=user_agent,
        )
        await self._transaction.commit()

        lien = f"{self._reset_policy.frontend_reset_url}?token={secret}"
        background_tasks.add_task(self._envoie_email_reset, compte.email, lien)

    async def _envoie_email_reset(self, email: str, reset_url: str) -> None:
        try:
            await self._mailer.send_password_reset_email(to=email, reset_url=reset_url)
        except Exception:
            logger.exception("auth.password_reset.mail_failed")

    async def confirm_password_reset(
        self, *, token: str, new_password: str, client_ip: str | None, user_agent: str | None
    ) -> AuthenticatedSession:
        revendique = await self._reset_tokens.consume(fingerprint_refresh(token))
        if revendique is None:
            raise InvalidOrExpiredResetTokenError("Lien invalide ou expiré")

        # Piège : le jeton peut avoir été émis avant une désactivation du compte. Sans cette
        # relecture, un lien encore valide (15 min) changerait quand même le mot de passe d'un
        # compte désactivé, réutilisable dès sa réactivation.
        compte = await self._users.get_by_id(revendique.user_id)
        if compte is None or not compte.is_active or compte.kind != AccountKind.HUMAIN.value:
            raise InvalidOrExpiredResetTokenError("Lien invalide ou expiré")

        await self._users.update_password(
            revendique.user_id, await self._hasher.hash(new_password), must_change_password=False
        )
        revoquees = await self._refresh.revoke_all_for_user(
            revendique.user_id, RevocationReason.CHANGEMENT_MOT_DE_PASSE
        )
        secret = await self._ouvre_une_famille(
            user_id=revendique.user_id, client_ip=client_ip, user_agent=user_agent
        )
        await self._audit.record(
            action=AuditAction.MOT_DE_PASSE_REINITIALISE_PAR_SOI,
            target_type="app_user",
            target_id=str(revendique.user_id),
            client_ip=client_ip,
            user_agent=user_agent,
            detail={"sessions_revoquees": revoquees},
        )
        await self._transaction.commit()

        compte = await self._users.get_by_id(revendique.user_id)
        if compte is None:
            raise SessionRejectedError("Compte introuvable")
        return self._session(self._en_principal(compte), secret)

    async def logout_all(self, principal: Principal) -> int:
        revoquees = await self._refresh.revoke_all_for_user(
            principal.id, RevocationReason.DECONNEXION
        )
        await self._audit.record(
            action=AuditAction.SESSIONS_REVOQUEES,
            actor=principal,
            detail={"sessions_revoquees": revoquees},
        )
        await self._transaction.commit()
        return revoquees

    def _session(self, principal: Principal, refresh_secret: str) -> AuthenticatedSession:
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
            refresh_secret=refresh_secret,
        )

    def _en_principal(self, compte: object) -> Principal:
        return Principal(
            id=compte.id,  # type: ignore[attr-defined]
            email=compte.email,  # type: ignore[attr-defined]
            role=Role(compte.role),  # type: ignore[attr-defined]
            kind=AccountKind(compte.kind),  # type: ignore[attr-defined]
            must_change_password=compte.must_change_password,  # type: ignore[attr-defined]
        )

    async def _ouvre_une_famille(
        self, *, user_id: UUID, client_ip: str | None, user_agent: str | None
    ) -> str:
        secret = generate_refresh_secret()
        await self._refresh.create(
            user_id=user_id,
            family_id=uuid4(),
            token_hash=fingerprint_refresh(secret),
            expires_at=datetime.now(UTC) + self._refresh_ttl,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        return secret

    async def _traite_rotation_refusee(
        self, empreinte: bytes, client_ip: str | None, user_agent: str | None
    ) -> NoReturn:
        ligne = await self._refresh.inspect(empreinte)
        if ligne is None:
            raise SessionRejectedError("Session inconnue")

        if ligne.expires_at <= datetime.now(UTC):
            raise SessionRejectedError("Session expirée")

        # Présenter un jeton déjà tourné est une preuve de compromission, pas un accident : toute
        # la famille tombe, y compris la session encore vivante du voleur ou de la victime.
        revoquees = await self._refresh.revoke_family(
            ligne.family_id, RevocationReason.REUTILISATION
        )
        await self._audit.record(
            action=AuditAction.REFRESH_REUTILISE,
            outcome=AuditOutcome.ECHEC,
            target_type="refresh_token",
            target_id=str(ligne.family_id),
            client_ip=client_ip,
            user_agent=user_agent,
            detail={"famille": str(ligne.family_id), "sessions_revoquees": revoquees},
        )
        await self._transaction.commit()
        raise SessionRejectedError("Session révoquée")

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
                outcome=AuditOutcome.ECHEC,
                actor_label=email.strip().lower(),
                client_ip=client_ip,
                user_agent=user_agent,
                detail={"motif": "seuil par identifiant depasse"},
            )
        await self._transaction.commit()
        raise RateLimitedError(politique.window_seconds)

    async def _refuse_si_limite_reset(self, *, email: str, client_ip: str | None) -> None:
        politique = self._reset_policy
        compteurs = await self._reset_attempts.count_recent(
            email=email, client_ip=client_ip, window_seconds=politique.window_seconds
        )

        depasse = (
            compteurs.per_identifier >= politique.max_requests_per_identifier
            or compteurs.per_ip >= politique.max_requests_per_ip
        )
        if not depasse:
            return

        await self._reset_attempts.record(email=email, client_ip=client_ip)
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
