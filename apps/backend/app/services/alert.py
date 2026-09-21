from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from app.models.energy import Alert, Prediction, Reading, Site
from app.repositories.alert import AlertRepository
from app.repositories.prediction import PredictionRepository
from app.repositories.reading import ReadingRepository
from app.repositories.site import SiteRepository

# Fenêtre de lectures/prédictions analysée à chaque exécution : assez large pour couvrir une paire
# de lectures consécutives (spike) et une coupure prolongée (outage), sans réanalyser tout
# l'historique à chaque lancement manuel du script de détection.
LOOKBACK = timedelta(hours=48)

# Cadence nominale d'une lecture : le CSV historique comme l'API Mock livrent un pas horaire.
EXPECTED_INTERVAL = timedelta(hours=1)
# Au-delà de trois pas manqués, on parle de coupure plutôt que d'un simple retard d'ingestion.
OUTAGE_THRESHOLD = EXPECTED_INTERVAL * 3

# +/-50% entre deux lectures consécutives du même site.
SPIKE_RELATIVE_THRESHOLD = 0.5
# 30% d'écart entre la consommation réelle et la prévision du même site/instant.
ANOMALY_RELATIVE_THRESHOLD = 0.3
# Une prévision quasi nulle rend l'écart relatif ininterprétable ; on l'ignore plutôt.
ANOMALY_MINIMUM_PREDICTED_VALUE = 1e-6

THRESHOLD_METRIC = "consumption_kw"
ANOMALY_METRIC = "consumption_kwh"
# `data_quality` -> sévérité du capteur défaillant. `good` est volontairement absent : il ne
# déclenche jamais d'alerte.
QUALITE_VERS_SEVERITE: dict[str, str] = {
    "partial": "low",
    "degraded": "medium",
    "critical": "critical",
}


class AlertService:
    def __init__(
        self,
        *,
        alerts: AlertRepository,
        readings: ReadingRepository,
        predictions: PredictionRepository,
        sites: SiteRepository,
    ) -> None:
        self._alerts = alerts
        self._readings = readings
        self._predictions = predictions
        self._sites = sites

    async def list_all(
        self, *, site_id: str | None = None, severity: str | None = None
    ) -> Sequence[Alert]:
        return await self._alerts.list_all(site_id=site_id, severity=severity)

    async def detect(
        self, *, now: datetime | None = None, site_id: str | None = None
    ) -> Sequence[Alert]:
        """Compare les lectures/prévisions récentes aux cinq règles internes et enregistre les
        alertes déclenchées (`source='enervision'`). Idempotent grâce à `source_alert_id` :
        rejouer sur une fenêtre déjà analysée ne recrée pas les mêmes lignes."""
        instant = now or datetime.now(UTC)
        depuis = instant - LOOKBACK

        sites = await self._sites.list_all()
        if site_id is not None:
            sites = [site for site in sites if site.site_id == site_id]
        sites_par_id = {site.site_id: site for site in sites}
        if not sites_par_id:
            return []

        lectures = [
            lecture
            for lecture in await self._readings.list_since(since=depuis, site_id=site_id)
            if lecture.site_id in sites_par_id
        ]
        predictions = [
            prediction
            for prediction in await self._predictions.list_since(since=depuis, site_id=site_id)
            if prediction.site_id in sites_par_id
        ]
        dernieres_lectures = {
            lecture.site_id: lecture
            for lecture in await self._readings.latest_by_site()
            if lecture.site_id in sites_par_id
        }

        candidates = [
            *_detect_threshold(lectures, sites_par_id),
            *_detect_spike(lectures),
            *_detect_anomaly(lectures, predictions),
            *_detect_outage(sites, dernieres_lectures, instant),
            *_detect_sensor(lectures),
        ]
        if not candidates:
            return []
        return await self._alerts.create_many(candidates)


def _severity_from_ratio(ratio: float) -> str:
    if ratio >= 2.0:
        return "critical"
    if ratio >= 1.5:
        return "high"
    if ratio >= 1.2:
        return "medium"
    return "low"


def _detect_threshold(lectures: Sequence[Reading], sites_par_id: dict[str, Site]) -> list[Alert]:
    # Seuil fixe = la capacité déclarée du site : dépasser `capacity_kw` est un dépassement
    # matériel, pas une simple variation, et évite un seuil arbitraire non fourni par le domaine.
    alertes = []
    for lecture in lectures:
        site = sites_par_id[lecture.site_id]
        valeur = lecture.consumption_kw
        if site.capacity_kw is None or site.capacity_kw <= 0 or valeur is None:
            continue
        if valeur <= site.capacity_kw:
            continue
        alertes.append(
            Alert(
                source_alert_id=f"threshold:{THRESHOLD_METRIC}:{lecture.timestamp.isoformat()}",
                site_id=lecture.site_id,
                source="enervision",
                timestamp=lecture.timestamp,
                type="threshold",
                severity=_severity_from_ratio(valeur / site.capacity_kw),
                message=(
                    f"Puissance appelée {valeur:.1f} kW au-dessus de la capacité du site "
                    f"({site.capacity_kw:.1f} kW)"
                ),
                value=valeur,
                threshold=site.capacity_kw,
                metric=THRESHOLD_METRIC,
                prediction_id=None,
                raw_data={},
            )
        )
    return alertes


def _detect_spike(lectures: Sequence[Reading]) -> list[Alert]:
    # `lectures` est triée par site, heure puis `reading_id` (cf. `ReadingRepository.list_since`) :
    # deux lignes consécutives du même site sont donc deux mesures consécutives dans le temps,
    # sauf lorsqu'elles partagent le même horodatage (deux `source` différentes pour le même
    # instant, permises par `uq_reading_source`) : ce n'est alors pas une variation réelle, on
    # l'ignore plutôt que de générer une fausse alerte figée par son `source_alert_id`.
    alertes = []
    precedente: Reading | None = None
    for lecture in lectures:
        if (
            precedente is None
            or precedente.site_id != lecture.site_id
            or precedente.timestamp == lecture.timestamp
        ):
            precedente = lecture
            continue
        avant, apres = precedente.consumption_kw, lecture.consumption_kw
        precedente = lecture
        if avant is None or apres is None:
            continue
        if avant == 0:
            # Une variation relative n'a pas de sens depuis zéro, mais un redémarrage direct à
            # une consommation positive reste le signal le plus alarmant du lot : `critical`
            # plutôt qu'un ratio indéfini.
            if apres > 0:
                alertes.append(_spike_alert(lecture, avant, apres, severity="critical"))
            continue
        variation = abs(apres - avant) / abs(avant)
        if variation < SPIKE_RELATIVE_THRESHOLD:
            continue
        alertes.append(
            _spike_alert(
                lecture,
                avant,
                apres,
                severity=_severity_from_ratio(variation / SPIKE_RELATIVE_THRESHOLD),
            )
        )
    return alertes


def _spike_alert(lecture: Reading, avant: float, apres: float, *, severity: str) -> Alert:
    return Alert(
        source_alert_id=f"spike:{THRESHOLD_METRIC}:{lecture.timestamp.isoformat()}",
        site_id=lecture.site_id,
        source="enervision",
        timestamp=lecture.timestamp,
        type="spike",
        severity=severity,
        message=(
            f"Variation brutale entre deux lectures consécutives ({avant:.1f} kW -> {apres:.1f} kW)"
        ),
        value=apres,
        threshold=avant,
        metric=THRESHOLD_METRIC,
        prediction_id=None,
        raw_data={},
    )


def _detect_anomaly(lectures: Sequence[Reading], predictions: Sequence[Prediction]) -> list[Alert]:
    # Alignement strict (site_id, target_at == timestamp) : `enervision_ml.score` produit une
    # cible à l'heure pile suivant la dernière lecture, sur la même grille horaire que `reading`.
    predictions_par_cle = {
        (prediction.site_id, prediction.target_at): prediction
        for prediction in predictions
        if prediction.target_metric == ANOMALY_METRIC
    }
    alertes = []
    for lecture in lectures:
        prediction = predictions_par_cle.get((lecture.site_id, lecture.timestamp))
        reel = lecture.consumption_kwh
        if prediction is None or reel is None or prediction.predicted_value is None:
            continue
        predite = prediction.predicted_value
        if abs(predite) < ANOMALY_MINIMUM_PREDICTED_VALUE:
            continue
        ecart = abs(reel - predite) / abs(predite)
        if ecart < ANOMALY_RELATIVE_THRESHOLD:
            continue
        alertes.append(
            Alert(
                source_alert_id=f"anomaly:{ANOMALY_METRIC}:{lecture.timestamp.isoformat()}",
                site_id=lecture.site_id,
                source="enervision",
                timestamp=lecture.timestamp,
                type="anomaly",
                severity=_severity_from_ratio(ecart / ANOMALY_RELATIVE_THRESHOLD),
                message=(
                    f"Écart de {ecart * 100:.0f}% entre la consommation mesurée ({reel:.1f} kWh) "
                    f"et la prévision ({predite:.1f} kWh)"
                ),
                value=reel,
                threshold=predite,
                metric=ANOMALY_METRIC,
                prediction_id=prediction.prediction_id,
                raw_data={},
            )
        )
    return alertes


def _detect_outage(
    sites: Sequence[Site], dernieres_lectures: dict[str, Reading], now: datetime
) -> list[Alert]:
    alertes = []
    for site in sites:
        derniere = dernieres_lectures.get(site.site_id)
        if derniere is None:
            alertes.append(
                _outage_alert(
                    site.site_id,
                    now,
                    reference=None,
                    message="Aucune lecture n'a jamais été reçue pour ce site",
                    severity="critical",
                )
            )
            continue
        absence = now - derniere.timestamp
        if absence < OUTAGE_THRESHOLD:
            continue
        alertes.append(
            _outage_alert(
                site.site_id,
                now,
                reference=derniere.timestamp,
                message=(
                    f"Aucune lecture depuis {absence} (dernière lecture : "
                    f"{derniere.timestamp.isoformat()})"
                ),
                severity=_severity_from_ratio(absence / OUTAGE_THRESHOLD),
            )
        )
    return alertes


def _outage_alert(
    site_id: str, now: datetime, *, reference: datetime | None, message: str, severity: str
) -> Alert:
    return Alert(
        source_alert_id=f"outage:{reference.isoformat() if reference is not None else 'jamais'}",
        site_id=site_id,
        source="enervision",
        timestamp=now,
        type="outage",
        severity=severity,
        message=message,
        value=None,
        threshold=None,
        metric=None,
        prediction_id=None,
        raw_data={},
    )


def _detect_sensor(lectures: Sequence[Reading]) -> list[Alert]:
    alertes = []
    for lecture in lectures:
        severite = QUALITE_VERS_SEVERITE.get(lecture.data_quality or "")
        if severite is None:
            continue
        raisons = ", ".join(lecture.null_reasons or []) or "raison non précisée"
        alertes.append(
            Alert(
                source_alert_id=f"sensor:{lecture.timestamp.isoformat()}",
                site_id=lecture.site_id,
                source="enervision",
                timestamp=lecture.timestamp,
                type="sensor",
                severity=severite,
                message=f"Qualité de mesure {lecture.data_quality} ({raisons})",
                value=None,
                threshold=None,
                metric=None,
                prediction_id=None,
                raw_data={},
            )
        )
    return alertes
