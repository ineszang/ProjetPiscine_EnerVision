from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import Alert


class AlertRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(
        self, *, site_id: str | None = None, severity: str | None = None
    ) -> Sequence[Alert]:
        requete = select(Alert).order_by(Alert.timestamp.desc(), Alert.alert_id.desc())
        if site_id is not None:
            requete = requete.where(Alert.site_id == site_id)
        if severity is not None:
            requete = requete.where(Alert.severity == severity)
        return (await self._session.scalars(requete)).all()

    async def create_many(self, alerts: Sequence[Alert]) -> Sequence[Alert]:
        # `ON CONFLICT DO NOTHING` sur `uq_alert_source_reference` : rejouer la détection sur une
        # fenêtre qui recouvre une exécution précédente ne doit pas dupliquer une alerte déjà
        # enregistrée. `RETURNING` ne renvoie donc que les lignes effectivement insérées.
        if not alerts:
            return []
        valeurs = [
            {
                "source_alert_id": alerte.source_alert_id,
                "site_id": alerte.site_id,
                "source": alerte.source,
                "timestamp": alerte.timestamp,
                "type": alerte.type,
                "severity": alerte.severity,
                "message": alerte.message,
                "value": alerte.value,
                "threshold": alerte.threshold,
                "metric": alerte.metric,
                "prediction_id": alerte.prediction_id,
                "raw_data": alerte.raw_data,
            }
            for alerte in alerts
        ]
        requete = (
            insert(Alert)
            .values(valeurs)
            .on_conflict_do_nothing(constraint="uq_alert_source_reference")
            .returning(Alert)
        )
        resultat = await self._session.execute(requete)
        await self._session.flush()
        return resultat.scalars().all()
