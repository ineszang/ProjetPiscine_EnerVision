# Piège : `change_role()` et `set_active()` refusent de toucher au dernier administrateur actif.
# Sans cette garde, un administrateur peut se rétrograder ou se désactiver lui-même, et plus
# personne ne peut administrer la plateforme sans repasser par `psql`.

import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.core.hashing import Argon2Hasher
from app.core.principal import Principal
from app.core.roles import Role
from app.models.audit_log import AuditAction
from app.models.refresh_token import RevocationReason
from app.models.user import AppUser
from app.repositories.audit_log import AuditLogRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository

LONGUEUR_MOT_DE_PASSE_TEMPORAIRE = 18


class Transaction(Protocol):
    async def commit(self) -> None: ...


class UserError(Exception):
    pass


class UserNotFoundError(UserError):
    pass


class EmailAlreadyUsedError(UserError):
    pass


class LastAdminError(UserError):
    pass


@dataclass(frozen=True, slots=True)
class CreatedUser:
    user: AppUser
    temporary_password: str


class UserService:
    def __init__(
        self,
        *,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        audit: AuditLogRepository,
        hasher: Argon2Hasher,
        transaction: Transaction,
    ) -> None:
        self._users = users
        self._refresh = refresh_tokens
        self._audit = audit
        self._hasher = hasher
        self._transaction = transaction

    async def list_all(self) -> Sequence[AppUser]:
        return await self._users.list_all()

    async def create(
        self, *, actor: Principal, email: str, role: Role, full_name: str | None
    ) -> CreatedUser:
        if await self._users.get_by_email(email) is not None:
            raise EmailAlreadyUsedError(email)

        provisoire = secrets.token_urlsafe(LONGUEUR_MOT_DE_PASSE_TEMPORAIRE)
        compte = await self._users.create(
            email=email,
            password_hash=await self._hasher.hash(provisoire),
            role=role,
            full_name=full_name,
            must_change_password=True,
        )
        await self._audit.record(
            action=AuditAction.COMPTE_CREE,
            actor=actor,
            target_type="app_user",
            target_id=str(compte.id),
            detail={"email": compte.email, "role_apres": role.value},
        )
        await self._transaction.commit()
        return CreatedUser(user=compte, temporary_password=provisoire)

    async def change_role(self, *, actor: Principal, user_id: UUID, role: Role) -> AppUser:
        compte = await self._exige(user_id)
        if compte.role == role.value:
            return compte

        await self._refuse_si_dernier_admin(compte, futur_role=role, futur_actif=compte.is_active)
        avant = compte.role
        await self._users.set_role(user_id, role)
        await self._refresh.revoke_all_for_user(user_id, RevocationReason.ADMINISTRATION)
        await self._audit.record(
            action=AuditAction.COMPTE_ROLE_CHANGE,
            actor=actor,
            target_type="app_user",
            target_id=str(user_id),
            detail={"role_avant": avant, "role_apres": role.value},
        )
        await self._transaction.commit()
        return await self._exige(user_id)

    async def set_active(self, *, actor: Principal, user_id: UUID, is_active: bool) -> AppUser:
        compte = await self._exige(user_id)
        if compte.is_active == is_active:
            return compte

        await self._refuse_si_dernier_admin(
            compte, futur_role=Role(compte.role), futur_actif=is_active
        )
        await self._users.set_active(user_id, is_active=is_active)
        if not is_active:
            await self._refresh.revoke_all_for_user(user_id, RevocationReason.ADMINISTRATION)
        await self._audit.record(
            action=AuditAction.COMPTE_ACTIVE if is_active else AuditAction.COMPTE_DESACTIVE,
            actor=actor,
            target_type="app_user",
            target_id=str(user_id),
        )
        await self._transaction.commit()
        return await self._exige(user_id)

    async def reset_password(self, *, actor: Principal, user_id: UUID) -> CreatedUser:
        compte = await self._exige(user_id)
        provisoire = secrets.token_urlsafe(LONGUEUR_MOT_DE_PASSE_TEMPORAIRE)

        await self._users.update_password(
            user_id, await self._hasher.hash(provisoire), must_change_password=True
        )
        await self._refresh.revoke_all_for_user(user_id, RevocationReason.CHANGEMENT_MOT_DE_PASSE)
        await self._audit.record(
            action=AuditAction.COMPTE_MOT_DE_PASSE_REINITIALISE,
            actor=actor,
            target_type="app_user",
            target_id=str(user_id),
            detail={"email": compte.email},
        )
        await self._transaction.commit()
        return CreatedUser(user=await self._exige(user_id), temporary_password=provisoire)

    async def _exige(self, user_id: UUID) -> AppUser:
        compte = await self._users.get_by_id(user_id)
        if compte is None:
            raise UserNotFoundError(str(user_id))
        return compte

    async def _refuse_si_dernier_admin(
        self, compte: AppUser, *, futur_role: Role, futur_actif: bool
    ) -> None:
        etait_admin = compte.role == Role.ADMIN.value and compte.is_active
        reste_admin = futur_role is Role.ADMIN and futur_actif
        if not etait_admin or reste_admin:
            return
        if await self._users.count_active_admins() <= 1:
            raise LastAdminError(str(compte.id))
