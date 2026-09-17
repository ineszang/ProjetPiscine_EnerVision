# Piège : `consume()` est une seule instruction, sur le modèle de `claim_for_rotation()` du
# jeton de rafraîchissement. Un SELECT puis un UPDATE laisseraient une fenêtre où deux
# soumissions concurrentes du même lien réussiraient toutes les deux.

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.password_reset_token import PasswordResetToken


@dataclass(frozen=True, slots=True)
class ConsumedResetToken:
    id: UUID
    user_id: UUID


class PasswordResetTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: UUID,
        token_hash: bytes,
        expires_at: datetime,
        client_ip: str | None,
        user_agent: str | None,
    ) -> PasswordResetToken:
        jeton = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        self._session.add(jeton)
        await self._session.flush()
        return jeton

    async def consume(self, token_hash: bytes) -> ConsumedResetToken | None:
        requete = (
            update(PasswordResetToken)
            .where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.consumed_at.is_(None),
                PasswordResetToken.expires_at > func.clock_timestamp(),
            )
            .values(consumed_at=func.clock_timestamp())
            .returning(PasswordResetToken.id, PasswordResetToken.user_id)
        )
        ligne = (await self._session.execute(requete)).one_or_none()
        if ligne is None:
            return None
        return ConsumedResetToken(id=ligne.id, user_id=ligne.user_id)

    async def invalidate_all_for_user(self, user_id: UUID) -> int:
        resultat = await self._session.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user_id, PasswordResetToken.consumed_at.is_(None))
            .values(consumed_at=func.clock_timestamp())
            .returning(PasswordResetToken.id)
        )
        return len(resultat.all())
