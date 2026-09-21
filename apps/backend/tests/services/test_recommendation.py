from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from app.models.energy import Alert, Recommendation
from app.repositories.recommendation import NouvelleRecommandation
from app.services.recommendation import RecommendationNotFoundError, RecommendationService

MOMENT = datetime(2024, 1, 1, tzinfo=UTC)


def recommendation(recommendation_id: int = 1) -> Recommendation:
    return Recommendation(
        recommendation_id=recommendation_id,
        alert_id=1,
        action="Vérifier la consommation",
        explanation="Pic détecté",
        rule_reference="spike-v1",
        created_at=MOMENT,
    )


def alerte(alert_id: int = 1, site_id: str = "SITE001", severity: str = "high") -> Alert:
    return Alert(
        alert_id=alert_id,
        source_alert_id=f"ALR-{alert_id}",
        site_id=site_id,
        source="api_mock",
        timestamp=MOMENT,
        type="spike",
        severity=severity,
        message="Pic de consommation",
        value=None,
        threshold=None,
        metric=None,
        prediction_id=None,
        raw_data={},
    )


class FakeRepository:
    def __init__(self, recommendations: list[Recommendation], creees: int | None = None) -> None:
        self._recommendations = recommendations
        self._creees = creees
        self.recues: list[NouvelleRecommandation] = []

    async def list_all(self) -> list[Recommendation]:
        return self._recommendations

    async def get_by_id(self, recommendation_id: int) -> Recommendation | None:
        return next(
            (r for r in self._recommendations if r.recommendation_id == recommendation_id), None
        )

    async def create_missing(self, nouvelles: Sequence[NouvelleRecommandation]) -> int:
        self.recues = list(nouvelles)
        return len(self.recues) if self._creees is None else self._creees


class FakeAlertRepository:
    def __init__(self, alertes: list[Alert]) -> None:
        self._alertes = alertes
        self.site_demande: str | None = None

    async def list_all(
        self, *, site_id: str | None = None, severity: str | None = None
    ) -> list[Alert]:
        self.site_demande = site_id
        if site_id is None:
            return self._alertes
        return [a for a in self._alertes if a.site_id == site_id]


class FakeTransaction:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


def service(
    recommendations: FakeRepository | None = None,
    alerts: FakeAlertRepository | None = None,
    transaction: FakeTransaction | None = None,
) -> RecommendationService:
    return RecommendationService(
        recommendations=recommendations or FakeRepository([]),
        alerts=alerts or FakeAlertRepository([]),
        transaction=transaction or FakeTransaction(),
    )


async def test_list_all_returns_the_repository_recommendations() -> None:
    depot = FakeRepository([recommendation(1), recommendation(2)])

    recommendations = await service(recommendations=depot).list_all()

    assert [r.recommendation_id for r in recommendations] == [1, 2]


async def test_get_by_id_returns_the_matching_recommendation() -> None:
    trouve = await service(recommendations=FakeRepository([recommendation(1)])).get_by_id(1)

    assert trouve.recommendation_id == 1


async def test_get_by_id_raises_when_the_recommendation_is_unknown() -> None:
    with pytest.raises(RecommendationNotFoundError):
        await service().get_by_id(404)


async def test_generate_persists_one_proposal_per_triggered_rule() -> None:
    depot = FakeRepository([])

    rapport = await service(
        recommendations=depot, alerts=FakeAlertRepository([alerte(severity="critical")])
    ).generate()

    assert {n.rule_reference for n in depot.recues} == {
        "spike-delestage-v1",
        "escalade-astreinte-v1",
    }
    assert rapport.recommandations_creees == 2


async def test_generate_commits_once() -> None:
    transaction = FakeTransaction()

    await service(alerts=FakeAlertRepository([alerte()]), transaction=transaction).generate()

    assert transaction.commits == 1


async def test_generate_restricts_the_alerts_to_the_requested_site() -> None:
    alertes = FakeAlertRepository([alerte(1, site_id="SITE001"), alerte(2, site_id="SITE002")])
    depot = FakeRepository([])

    rapport = await service(recommendations=depot, alerts=alertes).generate(site_id="SITE002")

    assert alertes.site_demande == "SITE002"
    assert rapport.alertes_examinees == 1
    assert {n.alert_id for n in depot.recues} == {2}


async def test_generate_reports_nothing_when_no_alert_matches() -> None:
    rapport = await service().generate()

    assert rapport.alertes_examinees == 0
    assert rapport.recommandations_creees == 0
    assert rapport.deja_presentes == 0


async def test_generate_counts_the_proposals_the_database_already_held() -> None:
    depot = FakeRepository([], creees=0)

    rapport = await service(
        recommendations=depot, alerts=FakeAlertRepository([alerte()])
    ).generate()

    assert rapport.recommandations_creees == 0
    assert rapport.deja_presentes == 1
