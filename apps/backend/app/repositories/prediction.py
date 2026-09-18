from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import Prediction


class PredictionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
