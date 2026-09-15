# Piège : `set_role()` et `set_active()` avancent `credentials_changed_at`. C'est ce qui rend
# un changement de rôle ou une désactivation effectifs à la requête suivante au lieu d'attendre
# l'expiration du jeton d'accès. Une mise à jour qui l'oublierait laisserait 15 minutes de
# privilèges périmés.

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import AccountKind, Role
from app.models.user import AppUser


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> AppUser | None:
        requete = select(AppUser).where(AppUser.email == email.strip().lower())
        return (await self._session.execute(requete)).scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> AppUser | None:
        return await self._session.get(AppUser, user_id)

    async def list_all(self) -> Sequence[AppUser]:
        requete = select(AppUser).order_by(AppUser.email)
        return (await self._session.execute(requete)).scalars().all()

    async def count_active_admins(self) -> int:
        requete = (
            select(func.count())
            .select_from(AppUser)
            .where(AppUser.role == Role.ADMIN.value, AppUser.is_active.is_(True))
        )
        return (await self._session.execute(requete)).scalar_one()

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        role: Role,
        kind: AccountKind = AccountKind.HUMAIN,
        full_name: str | None = None,
        must_change_password: bool = False,
    ) -> AppUser:
        compte = AppUser(
            email=email.strip().lower(),
            password_hash=password_hash,
            role=role.value,
            kind=kind.value,
            full_name=full_name,
            must_change_password=must_change_password,
        )
        self._session.add(compte)
        await self._session.flush()
        return compte

    async def update_password(
        self, user_id: UUID, password_hash: str, *, must_change_password: bool
    ) -> None:
        await self._session.execute(
            update(AppUser)
            .where(AppUser.id == user_id)
            .values(
                password_hash=password_hash,
                must_change_password=must_change_password,
                credentials_changed_at=func.clock_timestamp(),
            )
        )

    async def rehash_password(self, user_id: UUID, password_hash: str) -> None:
        # Un simple recalcul avec des paramètres Argon2 plus récents ne périme aucun jeton.
        await self._session.execute(
            update(AppUser).where(AppUser.id == user_id).values(password_hash=password_hash)
        )

    async def touch_last_login(self, user_id: UUID) -> None:
        await self._session.execute(
            update(AppUser).where(AppUser.id == user_id).values(last_login_at=func.now())
        )

    async def set_role(self, user_id: UUID, role: Role) -> None:
        await self._session.execute(
            update(AppUser)
            .where(AppUser.id == user_id)
            .values(role=role.value, credentials_changed_at=func.clock_timestamp())
        )

    async def set_active(self, user_id: UUID, *, is_active: bool) -> None:
        await self._session.execute(
            update(AppUser)
            .where(AppUser.id == user_id)
            .values(is_active=is_active, credentials_changed_at=func.clock_timestamp())
        )
