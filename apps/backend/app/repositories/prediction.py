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
        # Piège : `prediction` n'a pas d'unicité sur `(site_id, target_at)` (cf.
        # `enervision_ml.score`, qui insère toujours une nouvelle ligne plutôt que d'écraser la
        # précédente). `prediction_id` en dernier départage donc les égalités de `target_at` par
        # ordre croissant : `_detect_anomaly` construit un dict qui garde le dernier rencontré,
        # c'est-à-dire le run le plus récent plutôt qu'une ligne choisie au hasard par le plan
        # d'exécution.
        requete = (
            select(Prediction)
            .where(Prediction.target_at >= since, Prediction.status == "available")
            .order_by(Prediction.site_id, Prediction.target_at, Prediction.prediction_id)
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
