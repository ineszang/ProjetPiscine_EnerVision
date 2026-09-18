from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import Prediction


class PredictionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_since(
        self, *, since: datetime, site_id: str | None = None
    ) -> Sequence[Prediction]:
        # Restreint à `available` : une prévision `insufficient_data`/`error` n'a pas de
        # `predicted_value` à comparer à une lecture réelle (détection d'anomalie).
        requete = (
            select(Prediction)
            .where(Prediction.target_at >= since, Prediction.status == "available")
            .order_by(Prediction.site_id, Prediction.target_at)
        )
        if site_id is not None:
            requete = requete.where(Prediction.site_id == site_id)
        return (await self._session.scalars(requete)).all()

    async def latest_by_site(self) -> Sequence[Prediction]:
        # `.distinct(site_id)` compile en `DISTINCT ON (site_id)` sous PostgreSQL : une seule
        # ligne par site, la plus récente grâce à l'ordre composite qui suit. Même mécanisme que
        # `ReadingRepository.latest_by_site`. Trié sur `target_at` (couvert par
        # `ix_prediction_site_target`) plutôt que `created_at` : c'est la prévision la plus
        # récente qui compte pour un tableau de bord, pas forcément le dernier run de scoring.
        requete = (
            select(Prediction)
            .distinct(Prediction.site_id)
            .order_by(
                Prediction.site_id,
                Prediction.target_at.desc(),
                Prediction.prediction_id.desc(),
            )
        )
        return (await self._session.scalars(requete)).all()
