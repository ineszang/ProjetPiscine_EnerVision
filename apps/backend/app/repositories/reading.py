from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import Reading


class ReadingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def latest_by_site(self) -> Sequence[Reading]:
        # `.distinct(site_id)` compile en `DISTINCT ON (site_id)` sous PostgreSQL : une seule
        # ligne par site, la plus récente grâce à l'ordre composite qui suit. `reading_id` départage
        # les égalités de timestamp, que `uq_reading_source` autorise à `source` différente.
        requete = (
            select(Reading)
            .distinct(Reading.site_id)
            .order_by(Reading.site_id, Reading.timestamp.desc(), Reading.reading_id.desc())
        )
        return (await self._session.execute(requete)).scalars().all()

    async def latest_for_site(self, site_id: str) -> Reading | None:
        # Piège : `uq_reading_source` autorise deux lignes au même `site_id`+`timestamp` quand la
        # `source` diffère. Sans `reading_id` en départage, le `LIMIT 1` renverrait au hasard.
        requete = (
            select(Reading)
            .where(Reading.site_id == site_id)
            .order_by(Reading.timestamp.desc(), Reading.reading_id.desc())
            .limit(1)
        )
        lecture: Reading | None = await self._session.scalar(requete)
        return lecture

    async def list_since(self, *, since: datetime, site_id: str | None = None) -> Sequence[Reading]:
        # Trié par site puis par heure croissante : la détection d'alertes (spike) a besoin de
        # comparer chaque lecture à celle qui la précède immédiatement pour le même site.
        # `reading_id` en dernier départage : `uq_reading_source` autorise deux lignes au même
        # `site_id`+`timestamp` quand la `source` diffère (même piège que `latest_for_site`), sans
        # quoi l'ordre entre elles ne serait pas garanti d'un appel à l'autre.
        requete = (
            select(Reading)
            .where(Reading.timestamp >= since)
            .order_by(Reading.site_id, Reading.timestamp, Reading.reading_id)
        )
        if site_id is not None:
            requete = requete.where(Reading.site_id == site_id)
        return (await self._session.scalars(requete)).all()

    async def list_history(
        self,
        *,
        start: datetime,
        end: datetime,
        site_id: str | None = None,
        limit: int,
        offset: int,
    ) -> Sequence[Reading]:
        requete = (
            select(Reading)
            .where(Reading.timestamp >= start, Reading.timestamp < end)
            .order_by(Reading.timestamp.desc(), Reading.reading_id.desc())
            .limit(limit)
            .offset(offset)
        )
        if site_id is not None:
            requete = requete.where(Reading.site_id == site_id)
        return (await self._session.scalars(requete)).all()
