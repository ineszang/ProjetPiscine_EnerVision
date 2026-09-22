"""Contrainte : la dérive se mesure sur ce qui a déjà eu lieu - DriftService.evaluate()

Une prévision ne devient vérifiable que quand la lecture de son instant cible est ingérée. La
fenêtre est donc fermée à droite par un délai de grâce : sans lui, la dernière heure ferait
chuter le taux de couverture à chaque exécution, et le verdict dirait « dérive » alors que
seule l'ingestion n'avait pas fini son tour.

La comparaison se fait entre deux fenêtres vives de même durée, pas contre la métrique de
référence du modèle journalisée à l'entraînement. Ce ne sont pas les mêmes grandeurs :
l'entraînement mesure un backtest où la météo de l'heure cible est connue, le scoring prévoit
une heure future dont la météo ne l'est pas. Les comparer classerait le modèle « en dérive »
dès le premier jour, ce qui ne prouverait rien.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from app.models.energy import DriftReport
from app.repositories.drift import (
    ComptageStatut,
    DriftRepository,
    NouveauRapportDerive,
    PaireDerive,
)

STATUT_STABLE = "stable"
STATUT_DERIVE = "derive"
STATUT_INDETERMINE = "indetermine"

STATUT_INSUFFISANT = "insufficient_data"
STATUT_DISPONIBLE = "available"


@dataclass(frozen=True, slots=True)
class Seuils:
    # 168 h, la saisonnalité hebdomadaire que le modèle apprend par son lag principal : une
    # fenêtre plus courte comparerait un week-end à une semaine ouvrée.
    fenetre: timedelta = timedelta(hours=168)
    grace: timedelta = timedelta(hours=2)
    min_observations: int = 24
    ratio_derive: float = 1.25
    mae_plancher: float = 0.0
    seuil_biais: float = 0.0
    seuil_couverture: float = 0.8


@dataclass(frozen=True, slots=True)
class Metriques:
    n_observations: int
    mae: float | None
    mape: float | None
    bias: float | None
    model_references: list[str]


def mesure(paires: Sequence[PaireDerive]) -> Metriques:
    if not paires:
        return Metriques(n_observations=0, mae=None, mape=None, bias=None, model_references=[])

    ecarts = [paire.predicted_value - paire.actual_value for paire in paires]
    # Le MAPE diverge sur une consommation nulle : les sites à l'arrêt sortent de ce seul
    # rapport, jamais des autres métriques.
    ratios = [
        abs(ecart / paire.actual_value)
        for ecart, paire in zip(ecarts, paires, strict=True)
        if paire.actual_value != 0
    ]

    return Metriques(
        n_observations=len(paires),
        mae=sum(abs(ecart) for ecart in ecarts) / len(ecarts),
        mape=(sum(ratios) / len(ratios) * 100) if ratios else None,
        bias=sum(ecarts) / len(ecarts),
        model_references=sorted({paire.model_reference for paire in paires}),
    )


@dataclass(frozen=True, slots=True)
class Verdict:
    status: str
    reason: str | None


class DriftService:
    def __init__(self, depot: DriftRepository, *, seuils: Seuils | None = None) -> None:
        self._depot = depot
        self._seuils = seuils or Seuils()

    async def derniers(self, *, site_id: str | None = None) -> Sequence[DriftReport]:
        """Ce que sert l'API : le dernier rapport de chaque site, plus la ligne globale."""
        return await self._depot.derniers(site_id=site_id)

    async def evaluate(
        self, *, now: datetime | None = None, site_id: str | None = None
    ) -> list[NouveauRapportDerive]:
        """Une ligne par site, plus une ligne globale dont le `site_id` est nul."""
        fin = (now or datetime.now(UTC)) - self._seuils.grace
        debut = fin - self._seuils.fenetre
        reference_fin = debut
        reference_debut = reference_fin - self._seuils.fenetre

        recentes = await self._depot.paires(debut=debut, fin=fin, site_id=site_id)
        anciennes = await self._depot.paires(
            debut=reference_debut, fin=reference_fin, site_id=site_id
        )
        comptages = await self._depot.comptages(debut=debut, fin=fin, site_id=site_id)

        gabarit = NouveauRapportDerive(
            site_id=None,
            window_start=debut,
            window_end=fin,
            reference_start=reference_debut,
            reference_end=reference_fin,
            n_observations=0,
            mae=None,
            mape=None,
            bias=None,
            reference_mae=None,
            coverage_ratio=None,
            insufficient_data_ratio=None,
            model_references=[],
            status=STATUT_INDETERMINE,
            reason=None,
        )

        rapports = [
            self._rapport(
                gabarit,
                site=site,
                recentes=[p for p in recentes if p.site_id == site],
                anciennes=[p for p in anciennes if p.site_id == site],
                comptages=[c for c in comptages if c.site_id == site],
            )
            for site in sorted(
                {paire.site_id for paire in recentes} | {c.site_id for c in comptages}
            )
        ]
        rapports.append(
            self._rapport(
                gabarit, site=None, recentes=recentes, anciennes=anciennes, comptages=comptages
            )
        )
        return rapports

    def _rapport(
        self,
        gabarit: NouveauRapportDerive,
        *,
        site: str | None,
        recentes: Sequence[PaireDerive],
        anciennes: Sequence[PaireDerive],
        comptages: Sequence[ComptageStatut],
    ) -> NouveauRapportDerive:
        metriques = mesure(recentes)
        reference = mesure(anciennes)
        couverture = _couverture(len(recentes), comptages)
        verdict = self._verdict(metriques, reference_mae=reference.mae, couverture=couverture)

        return replace(
            gabarit,
            site_id=site,
            n_observations=metriques.n_observations,
            mae=metriques.mae,
            mape=metriques.mape,
            bias=metriques.bias,
            reference_mae=reference.mae,
            coverage_ratio=couverture,
            insufficient_data_ratio=_part_insuffisante(comptages),
            model_references=metriques.model_references,
            status=verdict.status,
            reason=verdict.reason,
        )

    def _verdict(
        self, metriques: Metriques, *, reference_mae: float | None, couverture: float | None
    ) -> Verdict:
        seuils = self._seuils
        if metriques.n_observations < seuils.min_observations:
            return Verdict(
                STATUT_INDETERMINE,
                f"{metriques.n_observations} prévision(s) vérifiée(s) sur la fenêtre, "
                f"minimum {seuils.min_observations}.",
            )

        if couverture is not None and couverture < seuils.seuil_couverture:
            return Verdict(
                STATUT_DERIVE,
                f"Couverture de {couverture:.0%}, sous le seuil de {seuils.seuil_couverture:.0%} : "
                "le pipeline, pas le modèle.",
            )

        plafond = _plafond(reference_mae, ratio=seuils.ratio_derive, plancher=seuils.mae_plancher)
        if metriques.mae is not None and plafond is not None and metriques.mae > plafond:
            return Verdict(
                STATUT_DERIVE,
                f"MAE de {metriques.mae:.2f} kWh au-delà de {plafond:.2f} kWh, "
                "seuil dérivé de la fenêtre de référence.",
            )

        if (
            seuils.seuil_biais > 0
            and metriques.bias is not None
            and abs(metriques.bias) > seuils.seuil_biais
        ):
            return Verdict(
                STATUT_DERIVE,
                f"Biais de {metriques.bias:+.2f} kWh : le modèle se trompe toujours du même côté.",
            )

        return Verdict(STATUT_STABLE, None)


def _plafond(reference_mae: float | None, *, ratio: float, plancher: float) -> float | None:
    if reference_mae is None:
        return plancher or None
    return max(plancher, reference_mae * ratio)


def _couverture(apparie: int, comptages: Sequence[ComptageStatut]) -> float | None:
    """Part des prévisions disponibles qui ont trouvé leur réalisé. Mesure l'ingestion et
    l'ordonnancement, pas la qualité du modèle."""
    disponibles = sum(c.nombre for c in comptages if c.status == STATUT_DISPONIBLE)
    return apparie / disponibles if disponibles else None


def _part_insuffisante(comptages: Sequence[ComptageStatut]) -> float | None:
    total = sum(c.nombre for c in comptages)
    if not total:
        return None
    return sum(c.nombre for c in comptages if c.status == STATUT_INSUFFISANT) / total
