from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.password_reset_attempt import PasswordResetAttempt


@dataclass(frozen=True, slots=True)
class ResetRequestCounts:
    per_identifier: int
    per_ip: int


class PasswordResetAttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, *, email: str, client_ip: str | None) -> None:
        self._session.add(
            PasswordResetAttempt(email_tried=email.strip().lower(), client_ip=client_ip)
        )

    async def count_recent(
        self, *, email: str, client_ip: str | None, window_seconds: int
    ) -> ResetRequestCounts:
        identifiant = email.strip().lower()
        meme_email = PasswordResetAttempt.email_tried == identifiant
        meme_ip = PasswordResetAttempt.client_ip == client_ip

        requete = select(
            func.count().filter(meme_email),
            func.count().filter(meme_ip),
        ).where(
            PasswordResetAttempt.occurred_at
            > datetime.now(UTC) - timedelta(seconds=window_seconds),
            meme_email | meme_ip,
        )

        par_identifiant, par_ip = (await self._session.execute(requete)).one()
        return ResetRequestCounts(per_identifier=par_identifiant, per_ip=par_ip)
