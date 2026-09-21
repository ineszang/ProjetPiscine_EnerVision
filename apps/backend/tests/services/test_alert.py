from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.models.energy import Alert
from app.services.alert import OUTAGE_THRESHOLD, AlertService, _severity_from_ratio

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


def alert(
    alert_id: int = 1,
    site_id: str = "site-1",
    severity: str = "high",
) -> Alert:
    return Alert(
        alert_id=alert_id,
        source_alert_id=f"ALR-{alert_id}",
        site_id=site_id,
        source="enervision",
        timestamp=datetime(2026, 9, 16, tzinfo=UTC),
        type="threshold",
        severity=severity,
        message="Dépassement du seuil configuré",
        value=812.5,
        threshold=720.0,
        metric="consumption_kw",
        prediction_id=None,
        raw_data={},
    )


@dataclass
class FauxSite:
    site_id: str
    capacity_kw: float | None = None


@dataclass
class FauxLecture:
    site_id: str
    timestamp: datetime
    consumption_kw: float | None = None
    consumption_kwh: float | None = None
    data_quality: str | None = None
    null_reasons: list[str] | None = None


@dataclass
class FauxPrediction:
    site_id: str
    target_at: datetime
    predicted_value: float | None
    target_metric: str = "consumption_kwh"
    prediction_id: int = 1


class FakeRepository:
    def __init__(self, alerts: list[Alert]) -> None:
        self._alerts = alerts
        self.appels: list[tuple[str | None, str | None]] = []
        self.crees: list[Alert] = []

    async def list_all(
        self, *, site_id: str | None = None, severity: str | None = None
    ) -> list[Alert]:
        self.appels.append((site_id, severity))
        return self._alerts

    async def create_many(self, alerts: list[Alert]) -> list[Alert]:
        self.crees = list(alerts)
        return self.crees


@dataclass
class FauxDepotLectures:
    depuis: list[FauxLecture] = field(default_factory=list)
    dernieres: list[FauxLecture] = field(default_factory=list)

    async def list_since(self, *, since: datetime, site_id: str | None = None) -> list[FauxLecture]:
        return [lecture for lecture in self.depuis if site_id is None or lecture.site_id == site_id]

    async def latest_by_site(self) -> list[FauxLecture]:
        return self.dernieres


@dataclass
class FauxDepotPredictions:
    predictions: list[FauxPrediction] = field(default_factory=list)

    async def list_since(
        self, *, since: datetime, site_id: str | None = None
    ) -> list[FauxPrediction]:
        return [p for p in self.predictions if site_id is None or p.site_id == site_id]


@dataclass
class FauxDepotSites:
    sites: list[FauxSite]

    async def list_all(self) -> list[FauxSite]:
        return self.sites


def service(
    *,
    sites: list[FauxSite],
    lectures: list[FauxLecture] | None = None,
    dernieres: list[FauxLecture] | None = None,
    predictions: list[FauxPrediction] | None = None,
    alerts: FakeRepository | None = None,
) -> tuple[AlertService, FakeRepository]:
    depot_alertes = alerts or FakeRepository([])
    dernieres_lectures = dernieres if dernieres is not None else (lectures or [])
    return (
        AlertService(
            alerts=depot_alertes,  # type: ignore[arg-type]
            readings=FauxDepotLectures(depuis=lectures or [], dernieres=dernieres_lectures),  # type: ignore[arg-type]
            predictions=FauxDepotPredictions(predictions or []),  # type: ignore[arg-type]
            sites=FauxDepotSites(sites),  # type: ignore[arg-type]
        ),
        depot_alertes,
    )


async def test_list_all_returns_the_repository_alerts() -> None:
    svc, _ = service(sites=[], alerts=FakeRepository([alert(1), alert(2)]))

    alertes = await svc.list_all()

    assert [a.alert_id for a in alertes] == [1, 2]


async def test_list_all_relays_the_filters_to_the_repository() -> None:
    depot = FakeRepository([])
    svc, _ = service(sites=[], alerts=depot)

    await svc.list_all(site_id="site-1", severity="critical")

    assert depot.appels == [("site-1", "critical")]


async def test_detect_raises_a_threshold_alert_above_site_capacity() -> None:
    svc, depot = service(
        sites=[FauxSite("A", capacity_kw=100.0)],
        lectures=[FauxLecture("A", NOW, consumption_kw=150.0)],
    )

    await svc.detect(now=NOW)

    (candidate,) = depot.crees
    assert candidate.type == "threshold"
    assert candidate.severity == "high"
    assert candidate.value == 150.0
    assert candidate.threshold == 100.0
    assert candidate.metric == "consumption_kw"


async def test_detect_ignores_a_reading_within_capacity() -> None:
    svc, depot = service(
        sites=[FauxSite("A", capacity_kw=100.0)],
        lectures=[FauxLecture("A", NOW, consumption_kw=80.0)],
    )

    await svc.detect(now=NOW)

    assert depot.crees == []


async def test_detect_ignores_threshold_when_the_site_has_no_declared_capacity() -> None:
    svc, depot = service(
        sites=[FauxSite("A", capacity_kw=None)],
        lectures=[FauxLecture("A", NOW, consumption_kw=9999.0)],
    )

    await svc.detect(now=NOW)

    assert depot.crees == []


async def test_detect_raises_a_spike_alert_on_a_brutal_consecutive_variation() -> None:
    svc, depot = service(
        sites=[FauxSite("A")],
        lectures=[
            FauxLecture("A", NOW - timedelta(hours=1), consumption_kw=100.0),
            FauxLecture("A", NOW, consumption_kw=160.0),
        ],
    )

    await svc.detect(now=NOW)

    (candidate,) = [a for a in depot.crees if a.type == "spike"]
    assert candidate.value == 160.0
    assert candidate.threshold == 100.0
    assert candidate.timestamp == NOW


async def test_detect_ignores_a_moderate_consecutive_variation() -> None:
    svc, depot = service(
        sites=[FauxSite("A")],
        lectures=[
            FauxLecture("A", NOW - timedelta(hours=1), consumption_kw=100.0),
            FauxLecture("A", NOW, consumption_kw=110.0),
        ],
    )

    await svc.detect(now=NOW)

    assert [a for a in depot.crees if a.type == "spike"] == []


async def test_detect_never_compares_consecutive_readings_across_two_sites() -> None:
    svc, depot = service(
        sites=[FauxSite("A"), FauxSite("B")],
        lectures=[
            FauxLecture("A", NOW - timedelta(hours=1), consumption_kw=10.0),
            FauxLecture("B", NOW, consumption_kw=1000.0),
        ],
    )

    await svc.detect(now=NOW)

    assert [a for a in depot.crees if a.type == "spike"] == []


async def test_detect_raises_an_anomaly_alert_far_from_the_matching_prediction() -> None:
    svc, depot = service(
        sites=[FauxSite("A")],
        lectures=[FauxLecture("A", NOW, consumption_kwh=100.0)],
        predictions=[FauxPrediction("A", target_at=NOW, predicted_value=70.0)],
    )

    await svc.detect(now=NOW)

    (candidate,) = [a for a in depot.crees if a.type == "anomaly"]
    assert candidate.value == 100.0
    assert candidate.threshold == 70.0
    assert candidate.metric == "consumption_kwh"
    assert candidate.prediction_id == 1


async def test_detect_ignores_a_reading_close_to_its_prediction() -> None:
    svc, depot = service(
        sites=[FauxSite("A")],
        lectures=[FauxLecture("A", NOW, consumption_kwh=100.0)],
        predictions=[FauxPrediction("A", target_at=NOW, predicted_value=95.0)],
    )

    await svc.detect(now=NOW)

    assert [a for a in depot.crees if a.type == "anomaly"] == []


async def test_detect_ignores_a_prediction_whose_target_at_does_not_match_the_reading() -> None:
    svc, depot = service(
        sites=[FauxSite("A")],
        lectures=[FauxLecture("A", NOW, consumption_kwh=100.0)],
        predictions=[FauxPrediction("A", target_at=NOW - timedelta(hours=1), predicted_value=1.0)],
    )

    await svc.detect(now=NOW)

    assert [a for a in depot.crees if a.type == "anomaly"] == []


async def test_detect_keeps_the_most_recent_run_when_two_predictions_share_the_same_target() -> (
    None
):
    # `PredictionRepository.list_since` départage les égalités de `target_at` par `prediction_id`
    # croissant : le repository fait donc déjà passer le run le plus récent en dernier dans la
    # liste, et c'est ce dernier que le dict de `_detect_anomaly` doit retenir.
    svc, depot = service(
        sites=[FauxSite("A")],
        lectures=[FauxLecture("A", NOW, consumption_kwh=100.0)],
        predictions=[
            FauxPrediction("A", target_at=NOW, predicted_value=100.0, prediction_id=1),
            FauxPrediction("A", target_at=NOW, predicted_value=70.0, prediction_id=2),
        ],
    )

    await svc.detect(now=NOW)

    (candidate,) = [a for a in depot.crees if a.type == "anomaly"]
    assert candidate.threshold == 70.0
    assert candidate.prediction_id == 2


async def test_detect_raises_an_outage_alert_past_the_threshold() -> None:
    derniere = NOW - OUTAGE_THRESHOLD - timedelta(minutes=1)
    svc, depot = service(
        sites=[FauxSite("A")],
        lectures=[],
        dernieres=[FauxLecture("A", derniere)],
    )

    await svc.detect(now=NOW)

    (candidate,) = [a for a in depot.crees if a.type == "outage"]
    assert candidate.severity in {"low", "medium", "high", "critical"}


async def test_detect_ignores_a_site_still_within_the_outage_threshold() -> None:
    derniere = NOW - OUTAGE_THRESHOLD + timedelta(minutes=1)
    svc, depot = service(
        sites=[FauxSite("A")],
        lectures=[],
        dernieres=[FauxLecture("A", derniere)],
    )

    await svc.detect(now=NOW)

    assert [a for a in depot.crees if a.type == "outage"] == []


async def test_detect_raises_a_critical_outage_alert_for_a_site_never_read() -> None:
    svc, depot = service(sites=[FauxSite("A")], lectures=[], dernieres=[])

    await svc.detect(now=NOW)

    (candidate,) = [a for a in depot.crees if a.type == "outage"]
    assert candidate.severity == "critical"
    assert candidate.source_alert_id == "outage:jamais"


async def test_detect_raises_a_sensor_alert_on_a_degraded_reading() -> None:
    svc, depot = service(
        sites=[FauxSite("A")],
        lectures=[FauxLecture("A", NOW, data_quality="critical", null_reasons=["missing:x"])],
    )

    await svc.detect(now=NOW)

    (candidate,) = [a for a in depot.crees if a.type == "sensor"]
    assert candidate.severity == "critical"


async def test_detect_ignores_a_good_quality_reading_for_the_sensor_rule() -> None:
    svc, depot = service(
        sites=[FauxSite("A")],
        lectures=[FauxLecture("A", NOW, data_quality="good")],
    )

    await svc.detect(now=NOW)

    assert [a for a in depot.crees if a.type == "sensor"] == []


async def test_detect_scopes_to_a_single_site_when_asked() -> None:
    svc, depot = service(
        sites=[FauxSite("A", capacity_kw=100.0), FauxSite("B", capacity_kw=100.0)],
        lectures=[
            FauxLecture("A", NOW, consumption_kw=150.0),
            FauxLecture("B", NOW, consumption_kw=150.0),
        ],
    )

    await svc.detect(now=NOW, site_id="A")

    assert {a.site_id for a in depot.crees} == {"A"}


async def test_detect_returns_early_when_there_is_no_site() -> None:
    svc, depot = service(sites=[])

    resultat = await svc.detect(now=NOW)

    assert resultat == []
    assert depot.crees == []


async def test_detect_ignores_a_spike_pair_with_a_missing_measurement() -> None:
    svc, depot = service(
        sites=[FauxSite("A")],
        lectures=[
            FauxLecture("A", NOW - timedelta(hours=1), consumption_kw=None),
            FauxLecture("A", NOW, consumption_kw=160.0),
        ],
    )

    await svc.detect(now=NOW)

    assert [a for a in depot.crees if a.type == "spike"] == []


async def test_detect_ignores_a_reading_still_at_zero_after_a_previous_zero() -> None:
    svc, depot = service(
        sites=[FauxSite("A")],
        lectures=[
            FauxLecture("A", NOW - timedelta(hours=1), consumption_kw=0.0),
            FauxLecture("A", NOW, consumption_kw=0.0),
        ],
    )

    await svc.detect(now=NOW)

    assert [a for a in depot.crees if a.type == "spike"] == []


async def test_detect_raises_a_critical_spike_when_a_site_restarts_from_zero() -> None:
    svc, depot = service(
        sites=[FauxSite("A")],
        lectures=[
            FauxLecture("A", NOW - timedelta(hours=1), consumption_kw=0.0),
            FauxLecture("A", NOW, consumption_kw=50.0),
        ],
    )

    await svc.detect(now=NOW)

    (candidate,) = [a for a in depot.crees if a.type == "spike"]
    assert candidate.severity == "critical"
    assert candidate.value == 50.0
    assert candidate.threshold == 0.0


async def test_detect_ignores_a_spike_pair_sharing_the_same_timestamp() -> None:
    svc, depot = service(
        sites=[FauxSite("A")],
        lectures=[
            FauxLecture("A", NOW, consumption_kw=100.0),
            FauxLecture("A", NOW, consumption_kw=160.0),
        ],
    )

    await svc.detect(now=NOW)

    assert [a for a in depot.crees if a.type == "spike"] == []


async def test_detect_ignores_an_anomaly_when_the_prediction_is_near_zero() -> None:
    svc, depot = service(
        sites=[FauxSite("A")],
        lectures=[FauxLecture("A", NOW, consumption_kwh=5.0)],
        predictions=[FauxPrediction("A", target_at=NOW, predicted_value=0.0)],
    )

    await svc.detect(now=NOW)

    assert [a for a in depot.crees if a.type == "anomaly"] == []


def test_severity_from_ratio_covers_every_band() -> None:
    assert _severity_from_ratio(1.0) == "low"
    assert _severity_from_ratio(1.2) == "medium"
    assert _severity_from_ratio(1.5) == "high"
    assert _severity_from_ratio(2.0) == "critical"


async def test_detect_does_not_call_create_many_when_nothing_triggers() -> None:
    svc, depot = service(
        sites=[FauxSite("A", capacity_kw=100.0)],
        lectures=[FauxLecture("A", NOW, consumption_kw=10.0, data_quality="good")],
    )

    resultat = await svc.detect(now=NOW)

    assert resultat == []
    assert depot.crees == []
