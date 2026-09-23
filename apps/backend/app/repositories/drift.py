"""Piège : deux dédoublonnages, pas un - DriftRepository.paires()

`prediction` n'a pas d'unicité sur `(site_id, target_at)` : chaque run de scoring empile une
ligne de plus. `uq_reading_source` autorise de son côté deux lectures au même instant quand la
`source` diffère. Joindre les deux tables sans `DISTINCT ON` des deux côtés compterait donc la
même heure plusieurs fois, et la moyenne d'erreur pèserait ces sites en double.

On retient la prédiction du run le plus récent, celle que sert `GET /api/v1/predictions`, avec
`prediction_id` en départage : `created_at` vaut l'heure de début de transaction et ne
distingue pas deux lignes du même run.
"""

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime

from sqlalchemy import Subquery, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import DriftReport, Prediction, Reading

TARGET_METRIC = "consumption_kwh"
STATUT_DISPONIBLE = "available"


@dataclass(frozen=True, slots=True)
class PaireDerive:
    site_id: str
    target_at: datetime
    predicted_value: float
    actual_value: float
    model_reference: str


@dataclass(frozen=True, slots=True)
class NouveauRapportDerive:
    site_id: str | None
    window_start: datetime
    window_end: datetime
    reference_start: datetime | None
    reference_end: datetime | None
    n_observations: int
    mae: float | None
    mape: float | None
    bias: float | None
    reference_mae: float | None
    coverage_ratio: float | None
    insufficient_data_ratio: float | None
    model_references: list[str]
    status: str
    reason: str | None


@dataclass(frozen=True, slots=True)
class ComptageStatut:
    site_id: str
    status: str
    nombre: int


def _predictions_retenues(*, debut: datetime, fin: datetime, site_id: str | None) -> Subquery:
    requete = (
        select(
            Prediction.site_id,
            Prediction.target_at,
            Prediction.predicted_value,
            Prediction.model_reference,
            Prediction.status,
        )
        .distinct(Prediction.site_id, Prediction.target_at)
        .where(
            Prediction.target_metric == TARGET_METRIC,
            Prediction.target_at >= debut,
            Prediction.target_at < fin,
        )
        .order_by(Prediction.site_id, Prediction.target_at, Prediction.prediction_id.desc())
    )
    if site_id is not None:
        requete = requete.where(Prediction.site_id == site_id)
    return requete.subquery()


def _lectures_retenues(*, debut: datetime, fin: datetime, site_id: str | None) -> Subquery:
    requete = (
        select(Reading.site_id, Reading.timestamp, Reading.consumption_kwh)
        .distinct(Reading.site_id, Reading.timestamp)
        .where(
            Reading.timestamp >= debut,
            Reading.timestamp < fin,
            Reading.consumption_kwh.is_not(None),
        )
        .order_by(Reading.site_id, Reading.timestamp, Reading.reading_id.desc())
    )
    if site_id is not None:
        requete = requete.where(Reading.site_id == site_id)
    return requete.subquery()


class DriftRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def paires(
        self, *, debut: datetime, fin: datetime, site_id: str | None = None
    ) -> Sequence[PaireDerive]:
        predictions = _predictions_retenues(debut=debut, fin=fin, site_id=site_id)
        lectures = _lectures_retenues(debut=debut, fin=fin, site_id=site_id)
        requete = (
            select(
                predictions.c.site_id,
                predictions.c.target_at,
                predictions.c.predicted_value,
                lectures.c.consumption_kwh,
                predictions.c.model_reference,
            )
            .select_from(predictions)
            .join(
                lectures,
                (lectures.c.site_id == predictions.c.site_id)
                & (lectures.c.timestamp == predictions.c.target_at),
            )
            .where(predictions.c.status == STATUT_DISPONIBLE)
            .order_by(predictions.c.site_id, predictions.c.target_at)
        )

        lignes = await self._session.execute(requete)
        return [
            PaireDerive(
                site_id=ligne[0],
                target_at=ligne[1],
                predicted_value=ligne[2],
                actual_value=ligne[3],
                model_reference=ligne[4],
            )
            for ligne in lignes
        ]

    async def comptages(
        self, *, debut: datetime, fin: datetime, site_id: str | None = None
    ) -> Sequence[ComptageStatut]:
        predictions = _predictions_retenues(debut=debut, fin=fin, site_id=site_id)
        requete = (
            select(predictions.c.site_id, predictions.c.status, func.count())
            .select_from(predictions)
            .group_by(predictions.c.site_id, predictions.c.status)
        )

        lignes = await self._session.execute(requete)
        return [
            ComptageStatut(site_id=ligne[0], status=ligne[1], nombre=ligne[2]) for ligne in lignes
        ]

    # Pourquoi : l'idempotence est déléguée à `uq_drift_report_window` plutôt qu'à une lecture
    # préalable, comme pour les recommandations. Rejouer la commande sur la même fenêtre ne
    # duplique donc rien.
    async def enregistre(self, rapports: Sequence[NouveauRapportDerive]) -> int:
        if not rapports:
            return 0

        valeurs = [asdict(rapport) for rapport in rapports]
        requete = (
            insert(DriftReport)
            .values(valeurs)
            .on_conflict_do_nothing(
                index_elements=[DriftReport.window_end, func.coalesce(DriftReport.site_id, "")]
            )
            .returning(DriftReport.drift_report_id)
        )
        return len((await self._session.scalars(requete)).all())

    async def derniers(self, *, site_id: str | None = None) -> Sequence[DriftReport]:
        requete = (
            select(DriftReport)
            .distinct(DriftReport.site_id)
            .order_by(
                DriftReport.site_id,
                DriftReport.computed_at.desc(),
                DriftReport.drift_report_id.desc(),
            )
        )
        if site_id is not None:
            requete = requete.where(DriftReport.site_id == site_id)
        return (await self._session.scalars(requete)).all()
