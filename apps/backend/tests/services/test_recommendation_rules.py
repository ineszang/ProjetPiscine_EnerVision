from datetime import UTC, datetime

import pytest

from app.models.energy import Alert
from app.services.recommendation_rules import FACTEUR_DEPASSEMENT_MAJEUR, applique_les_regles

MOMENT = datetime(2024, 1, 1, tzinfo=UTC)


def alerte(
    *,
    alert_id: int = 1,
    type_alerte: str = "spike",
    severity: str = "high",
    value: float | None = None,
    threshold: float | None = None,
    metric: str | None = None,
    site_id: str = "SITE001",
) -> Alert:
    return Alert(
        alert_id=alert_id,
        source_alert_id=f"ALR-{alert_id}",
        site_id=site_id,
        source="api_mock",
        timestamp=MOMENT,
        type=type_alerte,
        severity=severity,
        message="Alerte de test",
        value=value,
        threshold=threshold,
        metric=metric,
        prediction_id=None,
        raw_data={},
    )


@pytest.mark.parametrize(
    ("type_alerte", "attendue"),
    [
        ("spike", "spike-delestage-v1"),
        ("threshold", "threshold-reduction-v1"),
        ("outage", "outage-secours-v1"),
        ("sensor", "sensor-maintenance-v1"),
        ("anomaly", "anomaly-verification-v1"),
    ],
    ids=["pic", "seuil", "coupure", "capteur", "anomalie"],
)
def test_each_alert_type_yields_its_own_rule(type_alerte: str, attendue: str) -> None:
    proposees = applique_les_regles(alerte(type_alerte=type_alerte))

    assert [p.rule_reference for p in proposees] == [attendue]


def test_a_critical_alert_adds_the_escalation_rule() -> None:
    proposees = applique_les_regles(alerte(severity="critical"))

    assert "escalade-astreinte-v1" in {p.rule_reference for p in proposees}


@pytest.mark.parametrize("severity", ["low", "medium", "high"], ids=["faible", "moyenne", "haute"])
def test_a_non_critical_alert_does_not_escalate(severity: str) -> None:
    proposees = applique_les_regles(alerte(severity=severity))

    assert "escalade-astreinte-v1" not in {p.rule_reference for p in proposees}


def test_a_large_overshoot_adds_the_contract_rule() -> None:
    proposees = applique_les_regles(
        alerte(value=720.0 * FACTEUR_DEPASSEMENT_MAJEUR, threshold=720.0)
    )

    assert "contrat-puissance-v1" in {p.rule_reference for p in proposees}


def test_an_overshoot_below_the_factor_does_not_add_the_contract_rule() -> None:
    proposees = applique_les_regles(alerte(value=800.0, threshold=720.0))

    assert "contrat-puissance-v1" not in {p.rule_reference for p in proposees}


@pytest.mark.parametrize(
    ("value", "threshold"),
    [(None, 720.0), (900.0, None), (900.0, 0.0), (900.0, -10.0)],
    ids=["sans mesure", "sans seuil", "seuil nul", "seuil negatif"],
)
def test_the_contract_rule_stays_silent_without_an_exploitable_threshold(
    value: float | None, threshold: float | None
) -> None:
    proposees = applique_les_regles(alerte(value=value, threshold=threshold))

    assert "contrat-puissance-v1" not in {p.rule_reference for p in proposees}


def test_the_explanation_quotes_the_measure_and_the_threshold() -> None:
    proposees = applique_les_regles(alerte(value=812.5, threshold=720.0, metric="consumption_kw"))

    assert "(consumption_kw mesurée à 812.5, seuil 720.0)" in proposees[0].explanation


def test_the_explanation_quotes_the_measure_alone_when_no_threshold_is_known() -> None:
    proposees = applique_les_regles(alerte(value=812.5, metric="consumption_kw"))

    assert "(consumption_kw mesurée à 812.5)" in proposees[0].explanation


def test_the_explanation_omits_the_measure_when_the_alert_carries_none() -> None:
    proposees = applique_les_regles(alerte())

    assert "(" not in proposees[0].explanation


def test_the_explanation_names_the_site() -> None:
    proposees = applique_les_regles(alerte(site_id="SITE042"))

    assert "SITE042" in proposees[0].explanation


def test_every_proposal_carries_the_alert_identifier() -> None:
    proposees = applique_les_regles(alerte(alert_id=77, severity="critical"))

    assert {p.alert_id for p in proposees} == {77}


def test_an_alert_never_yields_the_same_rule_twice() -> None:
    proposees = applique_les_regles(
        alerte(severity="critical", value=900.0, threshold=720.0, metric="consumption_kw")
    )

    assert len(proposees) == len({p.rule_reference for p in proposees})


def test_a_critical_alert_over_the_threshold_yields_the_three_rules() -> None:
    proposees = applique_les_regles(
        alerte(severity="critical", value=900.0, threshold=720.0, metric="consumption_kw")
    )

    assert {p.rule_reference for p in proposees} == {
        "spike-delestage-v1",
        "escalade-astreinte-v1",
        "contrat-puissance-v1",
    }
