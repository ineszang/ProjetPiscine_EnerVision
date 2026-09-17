from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from app.models.energy import Reading
from app.repositories.reading import ReadingRepository

FENETRE_PAR_DEFAUT = timedelta(hours=24)
FENETRE_MAXIMALE = timedelta(days=90)


class FenetreInverseeError(Exception):
    """`start` est postérieur ou égal à `end`."""


class FenetreTropLargeError(Exception):
    """L'écart entre `start` et `end` dépasse `FENETRE_MAXIMALE`."""


class ReadingService:
    def __init__(self, *, readings: ReadingRepository) -> None:
        self._readings = readings

    async def get_latest(self, site_id: str) -> Reading | None:
        return await self._readings.latest_for_site(site_id)

    async def list_history(
        self,
        *,
        site_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int,
        offset: int,
    ) -> Sequence[Reading]:
        debut, fin = self._resoudre_fenetre(start, end)
        return await self._readings.list_history(
            site_id=site_id, start=debut, end=fin, limit=limit, offset=offset
        )

    @staticmethod
    def _resoudre_fenetre(
        start: datetime | None, end: datetime | None
    ) -> tuple[datetime, datetime]:
        # Piège : un datetime naïf (sans fuseau dans la chaîne ISO reçue) fait échouer la
        # comparaison à `reading.timestamp` (`timestamptz`) au niveau du pilote, en 500 plutôt
        # qu'un refus propre. On le traite comme de l'UTC plutôt que de le rejeter.
        debut = _vers_utc(start)
        fin = _vers_utc(end) or datetime.now(UTC)
        if debut is None:
            debut = fin - FENETRE_PAR_DEFAUT

        if debut >= fin:
            raise FenetreInverseeError
        if fin - debut > FENETRE_MAXIMALE:
            raise FenetreTropLargeError
        return debut, fin


def _vers_utc(instant: datetime | None) -> datetime | None:
    if instant is None:
        return None
    return instant if instant.tzinfo is not None else instant.replace(tzinfo=UTC)
