# Piège : `claim_for_rotation()` est une seule instruction. Un SELECT puis un UPDATE
# laisseraient une fenêtre où deux onglets réussissent la même rotation. Zéro ligne retournée
# signifie donc, sans ambiguïté, que le jeton était déjà tourné, révoqué, expiré ou inconnu, et
# c'est `inspect()` qui départage ensuite ces cas.

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken, RevocationReason


@dataclass(frozen=True, slots=True)
class ClaimedToken:
    id: UUID
    family_id: UUID
    user_id: UUID
    expires_at: datetime


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: UUID,
        family_id: UUID,
        token_hash: bytes,
        expires_at: datetime,
        client_ip: str | None,
        user_agent: str | None,
    ) -> RefreshToken:
        jeton = RefreshToken(
            user_id=user_id,
            family_id=family_id,
            token_hash=token_hash,
            expires_at=expires_at,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        self._session.add(jeton)
        await self._session.flush()
        return jeton

    async def claim_for_rotation(self, token_hash: bytes) -> ClaimedToken | None:
        requete = (
            update(RefreshToken)
            .where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.rotated_at.is_(None),
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > func.clock_timestamp(),
            )
            .values(
                rotated_at=func.clock_timestamp(),
                revoked_at=func.clock_timestamp(),
                revoked_reason=RevocationReason.ROTATION.value,
            )
            .returning(
                RefreshToken.id,
                RefreshToken.family_id,
                RefreshToken.user_id,
                RefreshToken.expires_at,
            )
        )
        ligne = (await self._session.execute(requete)).one_or_none()
        if ligne is None:
            return None
        return ClaimedToken(
            id=ligne.id,
            family_id=ligne.family_id,
            user_id=ligne.user_id,
            expires_at=ligne.expires_at,
        )

    async def inspect(self, token_hash: bytes) -> RefreshToken | None:
        requete = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return (await self._session.execute(requete)).scalar_one_or_none()

    async def link_replacement(self, ancien_id: UUID, nouveau_id: UUID) -> None:
        await self._session.execute(
            update(RefreshToken).where(RefreshToken.id == ancien_id).values(replaced_by=nouveau_id)
        )

    async def revoke_family(self, family_id: UUID, reason: RevocationReason) -> int:
        resultat = await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=func.clock_timestamp(), revoked_reason=reason.value)
            .returning(RefreshToken.id)
        )
        return len(resultat.all())

    async def revoke_all_for_user(self, user_id: UUID, reason: RevocationReason) -> int:
        resultat = await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=func.clock_timestamp(), revoked_reason=reason.value)
            .returning(RefreshToken.id)
        )
        return len(resultat.all())
