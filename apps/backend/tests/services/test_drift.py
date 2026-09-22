from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from app.repositories.drift import ComptageStatut, PaireDerive
from app.services.drift import (
    STATUT_DERIVE,
    STATUT_INDETERMINE,
    STATUT_STABLE,
    DriftService,
    Seuils,
    mesure,
)

INSTANT = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)


def paire(
    *, site_id: str = "SITE001", prevu: float, reel: float, reference: str = "lightgbm-aaa"
) -> PaireDerive:
    return PaireDerive(
        site_id=site_id,
        target_at=INSTANT,
        predicted_value=prevu,
        actual_value=reel,
        model_reference=reference,
    )


def paires(
    *, site_id: str = "SITE001", nombre: int, prevu: float, reel: float
) -> list[PaireDerive]:
    return [paire(site_id=site_id, prevu=prevu, reel=reel) for _ in range(nombre)]


class FauxDepot:
    def __init__(
        self,
        *,
        recentes: Sequence[PaireDerive] = (),
        anciennes: Sequence[PaireDerive] = (),
        comptages: Sequence[ComptageStatut] = (),
    ) -> None:
        self.recentes = list(recentes)
        self.anciennes = list(anciennes)
        self._comptages = list(comptages)
        self.fenetres: list[tuple[datetime, datetime]] = []

    async def paires(
        self, *, debut: datetime, fin: datetime, site_id: str | None = None
    ) -> Sequence[PaireDerive]:
        self.fenetres.append((debut, fin))
        return self.recentes if len(self.fenetres) == 1 else self.anciennes

    async def comptages(
        self, *, debut: datetime, fin: datetime, site_id: str | None = None
    ) -> Sequence[ComptageStatut]:
        return self._comptages


def service(depot: FauxDepot, **surcharges: object) -> DriftService:
    return DriftService(depot, seuils=Seuils(**surcharges))  # type: ignore[arg-type]


def test_drift_averages_the_absolute_gap_between_forecast_and_actual() -> None:
    metriques = mesure([paire(prevu=12.0, reel=10.0), paire(prevu=8.0, reel=10.0)])

    assert metriques.mae == 2.0
    assert metriques.n_observations == 2


def test_drift_computes_a_signed_bias_when_the_model_overforecasts() -> None:
    metriques = mesure([paire(prevu=12.0, reel=10.0), paire(prevu=14.0, reel=10.0)])

    assert metriques.bias == 3.0


def test_drift_computes_a_negative_bias_when_the_model_underforecasts() -> None:
    metriques = mesure([paire(prevu=8.0, reel=10.0), paire(prevu=6.0, reel=10.0)])

    assert metriques.bias == -3.0


def test_drift_excludes_a_zero_actual_from_the_mape_only() -> None:
    metriques = mesure([paire(prevu=11.0, reel=10.0), paire(prevu=5.0, reel=0.0)])

    assert metriques.mape == 10.0
    assert metriques.n_observations == 2
    assert metriques.mae == 3.0


def test_drift_reports_no_mape_when_every_actual_is_zero() -> None:
    metriques = mesure([paire(prevu=1.0, reel=0.0)])

    assert metriques.mape is None


def test_drift_lists_every_model_reference_seen_in_the_window() -> None:
    metriques = mesure(
        [paire(prevu=10.0, reel=10.0, reference="lightgbm-bbb"), paire(prevu=10.0, reel=10.0)]
    )

    assert metriques.model_references == ["lightgbm-aaa", "lightgbm-bbb"]


async def test_drift_reports_indetermine_when_the_window_holds_too_few_observations() -> None:
    depot = FauxDepot(recentes=paires(nombre=3, prevu=10.0, reel=10.0))

    rapports = await service(depot, min_observations=24).evaluate(now=INSTANT)

    assert {rapport.status for rapport in rapports} == {STATUT_INDETERMINE}
    assert all(rapport.reason for rapport in rapports)


async def test_drift_reports_derive_when_the_recent_mae_exceeds_the_reference_ratio() -> None:
    depot = FauxDepot(
        recentes=paires(nombre=30, prevu=14.0, reel=10.0),
        anciennes=paires(nombre=30, prevu=11.0, reel=10.0),
        comptages=[ComptageStatut(site_id="SITE001", status="available", nombre=30)],
    )

    rapports = await service(depot, min_observations=10).evaluate(now=INSTANT)

    global_ = next(rapport for rapport in rapports if rapport.site_id is None)
    assert global_.status == STATUT_DERIVE
    assert global_.mae == 4.0
    assert global_.reference_mae == 1.0


async def test_drift_reports_stable_when_the_recent_mae_stays_close_to_the_reference() -> None:
    depot = FauxDepot(
        recentes=paires(nombre=30, prevu=11.0, reel=10.0),
        anciennes=paires(nombre=30, prevu=11.0, reel=10.0),
        comptages=[ComptageStatut(site_id="SITE001", status="available", nombre=30)],
    )

    rapports = await service(depot, min_observations=10).evaluate(now=INSTANT)

    global_ = next(rapport for rapport in rapports if rapport.site_id is None)
    assert global_.status == STATUT_STABLE
    assert global_.reason is None


async def test_drift_reports_derive_when_the_coverage_ratio_falls_under_the_threshold() -> None:
    depot = FauxDepot(
        recentes=paires(nombre=30, prevu=10.0, reel=10.0),
        anciennes=paires(nombre=30, prevu=10.0, reel=10.0),
        comptages=[ComptageStatut(site_id="SITE001", status="available", nombre=100)],
    )

    rapports = await service(depot, min_observations=10).evaluate(now=INSTANT)

    global_ = next(rapport for rapport in rapports if rapport.site_id is None)
    assert global_.status == STATUT_DERIVE
    assert global_.coverage_ratio == 0.3


async def test_drift_reports_one_line_per_site_and_one_global_line() -> None:
    depot = FauxDepot(
        recentes=[
            *paires(site_id="SITE001", nombre=12, prevu=10.0, reel=10.0),
            *paires(site_id="SITE002", nombre=12, prevu=10.0, reel=10.0),
        ],
        comptages=[
            ComptageStatut(site_id="SITE001", status="available", nombre=12),
            ComptageStatut(site_id="SITE002", status="available", nombre=12),
        ],
    )

    rapports = await service(depot, min_observations=10).evaluate(now=INSTANT)

    assert [rapport.site_id for rapport in rapports] == ["SITE001", "SITE002", None]
    assert next(r for r in rapports if r.site_id is None).n_observations == 24


async def test_drift_measures_the_share_of_sites_left_without_enough_history() -> None:
    depot = FauxDepot(
        recentes=paires(nombre=30, prevu=10.0, reel=10.0),
        comptages=[
            ComptageStatut(site_id="SITE001", status="available", nombre=30),
            ComptageStatut(site_id="SITE001", status="insufficient_data", nombre=10),
        ],
    )

    rapports = await service(depot, min_observations=10).evaluate(now=INSTANT)

    assert next(r for r in rapports if r.site_id is None).insufficient_data_ratio == 0.25


async def test_drift_closes_the_window_before_the_grace_delay() -> None:
    depot = FauxDepot()

    await service(depot, grace=timedelta(hours=2), fenetre=timedelta(hours=168)).evaluate(
        now=INSTANT
    )

    recente, reference = depot.fenetres
    assert recente[1] == INSTANT - timedelta(hours=2)
    assert recente[0] == INSTANT - timedelta(hours=170)
    assert reference[1] == recente[0]


@pytest.mark.parametrize(
    ("prevu", "attendu"),
    [(10.0, STATUT_STABLE), (30.0, STATUT_DERIVE)],
    ids=["mae_stable", "mae_triplee"],
)
async def test_drift_compares_the_recent_window_to_the_reference_one(
    prevu: float, attendu: str
) -> None:
    depot = FauxDepot(
        recentes=paires(nombre=30, prevu=prevu, reel=10.0),
        anciennes=paires(nombre=30, prevu=10.0, reel=10.0),
        comptages=[ComptageStatut(site_id="SITE001", status="available", nombre=30)],
    )

    rapports = await service(depot, min_observations=10, mae_plancher=1.0).evaluate(now=INSTANT)

    assert next(r for r in rapports if r.site_id is None).status == attendu


async def test_drift_leaves_the_bias_out_of_the_verdict_by_default() -> None:
    # Le modèle surestime de 3 kWh à chaque heure, et le verdict reste `stable` : le biais est
    # mesuré et servi, il ne juge pas tant que `--bias-threshold` n'a pas été réglé (ADR 0011).
    depot = FauxDepot(
        recentes=paires(nombre=30, prevu=13.0, reel=10.0),
        anciennes=paires(nombre=30, prevu=13.0, reel=10.0),
        comptages=[ComptageStatut(site_id="SITE001", status="available", nombre=30)],
    )

    rapports = await service(depot, min_observations=10).evaluate(now=INSTANT)

    global_ = next(rapport for rapport in rapports if rapport.site_id is None)
    assert global_.status == STATUT_STABLE
    assert global_.bias == 3.0


@pytest.mark.parametrize(
    ("prevu", "attendu"),
    [(13.0, STATUT_DERIVE), (11.0, STATUT_STABLE)],
    ids=["biais_au_dela", "biais_sous_le_seuil"],
)
async def test_drift_reports_derive_on_the_bias_once_a_threshold_is_set(
    prevu: float, attendu: str
) -> None:
    # MAE récente et MAE de référence sont égales : seul le biais peut faire basculer le verdict.
    depot = FauxDepot(
        recentes=paires(nombre=30, prevu=prevu, reel=10.0),
        anciennes=paires(nombre=30, prevu=prevu, reel=10.0),
        comptages=[ComptageStatut(site_id="SITE001", status="available", nombre=30)],
    )

    rapports = await service(depot, min_observations=10, seuil_biais=2.0).evaluate(now=INSTANT)

    global_ = next(rapport for rapport in rapports if rapport.site_id is None)
    assert global_.status == attendu


async def test_drift_prefers_the_mae_reason_when_both_the_mae_and_the_bias_exceed() -> None:
    depot = FauxDepot(
        recentes=paires(nombre=30, prevu=20.0, reel=10.0),
        anciennes=paires(nombre=30, prevu=11.0, reel=10.0),
        comptages=[ComptageStatut(site_id="SITE001", status="available", nombre=30)],
    )

    rapports = await service(depot, min_observations=10, seuil_biais=2.0).evaluate(now=INSTANT)

    global_ = next(rapport for rapport in rapports if rapport.site_id is None)
    assert global_.status == STATUT_DERIVE
    assert "MAE" in (global_.reason or "")
