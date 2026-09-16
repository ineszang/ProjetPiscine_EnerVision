# Pourquoi : les trois compteurs tiennent en une seule requête, grâce aux clauses FILTER de
# PostgreSQL. Trois `count(*)` séparés feraient trois allers-retours sur le chemin critique de
# la connexion, qui est justement celui qu'un attaquant martèle.

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.login_attempt import LoginAttempt, LoginOutcome


@dataclass(frozen=True, slots=True)
class FailureCounts:
    per_identifier_and_ip: int
    per_ip: int
    per_identifier: int


class LoginAttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        email: str,
        client_ip: str | None,
        outcome: LoginOutcome,
        user_id: UUID | None = None,
    ) -> None:
        self._session.add(
            LoginAttempt(
                email_tried=email.strip().lower(),
                client_ip=client_ip,
                outcome=outcome.value,
                user_id=user_id,
            )
        )

    async def count_recent_failures(
        self, *, email: str, client_ip: str | None, window_seconds: int
    ) -> FailureCounts:
        identifiant = email.strip().lower()
        meme_email = LoginAttempt.email_tried == identifiant
        meme_ip = LoginAttempt.client_ip == client_ip

        requete = select(
            func.count().filter(and_(meme_email, meme_ip)),
            func.count().filter(meme_ip),
            func.count().filter(meme_email),
        ).where(
            LoginAttempt.outcome != LoginOutcome.SUCCES.value,
            LoginAttempt.occurred_at > datetime.now(UTC) - timedelta(seconds=window_seconds),
            meme_email | meme_ip,
        )

        par_identifiant_et_ip, par_ip, par_identifiant = (
            await self._session.execute(requete)
        ).one()
        return FailureCounts(
            per_identifier_and_ip=par_identifiant_et_ip,
            per_ip=par_ip,
            per_identifier=par_identifiant,
        )
