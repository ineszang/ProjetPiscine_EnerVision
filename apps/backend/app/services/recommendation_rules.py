# Piège : `rule_reference` est la clé d'idempotence en base, portée par la contrainte
# `uq_recommendation_alert_rule`. Renommer une référence déjà livrée ne remplace pas les
# recommandations existantes, il en crée de nouvelles à côté. Une règle qui change de sens
# prend donc une référence suffixée `-v2` - REGLES.

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from app.models.energy import Alert
from app.repositories.recommendation import NouvelleRecommandation
from app.schemas.alert import AlertSeverity, AlertType

FACTEUR_DEPASSEMENT_MAJEUR: Final = 1.2
POURCENTAGE_DEPASSEMENT_MAJEUR: Final = round((FACTEUR_DEPASSEMENT_MAJEUR - 1) * 100)


@dataclass(frozen=True, slots=True)
class Regle:
    reference: str
    action: str
    declencheur: Callable[[Alert], bool]
    motif: Callable[[Alert], str]


def _du_type(attendu: AlertType) -> Callable[[Alert], bool]:
    return lambda alerte: alerte.type == attendu


def _de_severite(attendue: AlertSeverity) -> Callable[[Alert], bool]:
    return lambda alerte: alerte.severity == attendue


# Un seuil nul ou négatif rendrait le rapport `value / threshold` arbitraire : l'alerte ne
# renseigne alors aucun dépassement exploitable, et la règle ne se déclenche pas.
def _depasse_largement_le_seuil(alerte: Alert) -> bool:
    if alerte.value is None or alerte.threshold is None or alerte.threshold <= 0:
        return False
    return alerte.value >= alerte.threshold * FACTEUR_DEPASSEMENT_MAJEUR


REGLES: Final[tuple[Regle, ...]] = (
    Regle(
        reference="spike-delestage-v1",
        action="Délester les équipements non prioritaires sur le créneau du pic",
        declencheur=_du_type(AlertType.SPIKE),
        motif=lambda alerte: f"Pic de consommation signalé sur le site {alerte.site_id}",
    ),
    Regle(
        reference="threshold-reduction-v1",
        action="Ramener la puissance appelée sous le seuil contractuel",
        declencheur=_du_type(AlertType.THRESHOLD),
        motif=lambda alerte: f"Seuil de consommation dépassé sur le site {alerte.site_id}",
    ),
    Regle(
        reference="outage-secours-v1",
        action="Basculer sur l'alimentation de secours et prévenir l'exploitant",
        declencheur=_du_type(AlertType.OUTAGE),
        motif=lambda alerte: (
            f"Risque de surcharge ou de coupure imminente sur le site {alerte.site_id}"
        ),
    ),
    Regle(
        reference="sensor-maintenance-v1",
        action="Planifier une intervention de maintenance sur le capteur",
        declencheur=_du_type(AlertType.SENSOR),
        motif=lambda alerte: (
            f"Capteur défaillant sur le site {alerte.site_id}, les mesures ne sont plus fiables"
        ),
    ),
    Regle(
        reference="anomaly-verification-v1",
        action="Confronter la mesure à la prévision et vérifier le paramétrage du site",
        declencheur=_du_type(AlertType.ANOMALY),
        motif=lambda alerte: (
            f"Écart anormal entre la mesure et le comportement attendu du site {alerte.site_id}"
        ),
    ),
    Regle(
        reference="escalade-astreinte-v1",
        action="Escalader à l'astreinte sous une heure",
        declencheur=_de_severite(AlertSeverity.CRITICAL),
        motif=lambda alerte: f"Alerte de sévérité critique sur le site {alerte.site_id}",
    ),
    Regle(
        reference="contrat-puissance-v1",
        action="Réévaluer la puissance souscrite au contrat",
        declencheur=_depasse_largement_le_seuil,
        motif=lambda alerte: (
            f"Dépassement d'au moins {POURCENTAGE_DEPASSEMENT_MAJEUR} % du seuil "
            f"sur le site {alerte.site_id}"
        ),
    ),
)


def applique_les_regles(alerte: Alert) -> list[NouvelleRecommandation]:
    contexte = _contexte_de_mesure(alerte)
    return [
        NouvelleRecommandation(
            alert_id=alerte.alert_id,
            action=regle.action,
            explanation=f"{regle.motif(alerte)}{contexte}.",
            rule_reference=regle.reference,
        )
        for regle in REGLES
        if regle.declencheur(alerte)
    ]


def _contexte_de_mesure(alerte: Alert) -> str:
    if alerte.value is None:
        return ""
    grandeur = alerte.metric or "valeur"
    if alerte.threshold is None:
        return f" ({grandeur} mesurée à {alerte.value})"
    return f" ({grandeur} mesurée à {alerte.value}, seuil {alerte.threshold})"
