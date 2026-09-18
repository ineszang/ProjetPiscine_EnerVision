from dataclasses import dataclass
from datetime import UTC, datetime

from app.services.prediction import PredictionService

TARGET_AT = datetime(2026, 9, 16, 13, 0, tzinfo=UTC)
CREATED_AT = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


@dataclass
class FauxSite:
    site_id: str
    site_name: str


@dataclass
class FauxPrediction:
    site_id: str
    target_at: datetime
    target_metric: str
    period_minutes: int | None
    predicted_value: float | None
    status: str
    failure_reason: str | None
    model_reference: str
    created_at: datetime


class FauxDepotSites:
    def __init__(self, sites: list[FauxSite]) -> None:
        self._sites = sites

    async def list_all(self) -> list[FauxSite]:
        return self._sites


class FauxDepotPredictions:
    def __init__(self, predictions: list[FauxPrediction]) -> None:
        self._predictions = predictions

    async def latest_by_site(self) -> list[FauxPrediction]:
        return self._predictions


def prediction_disponible(site_id: str = "A") -> FauxPrediction:
    return FauxPrediction(
        site_id=site_id,
        target_at=TARGET_AT,
        target_metric="consumption_kwh",
        period_minutes=60,
        predicted_value=812.5,
        status="available",
        failure_reason=None,
        model_reference="lightgbm-abc123",
        created_at=CREATED_AT,
    )


async def test_summary_attaches_the_latest_prediction_to_its_site() -> None:
    service = PredictionService(
        sites=FauxDepotSites([FauxSite("A", "Site A")]),  # type: ignore[arg-type]
        predictions=FauxDepotPredictions([prediction_disponible("A")]),  # type: ignore[arg-type]
    )

    resume = await service.summary()

    site = resume.sites[0]
    assert site.site_id == "A"
    assert site.prediction is not None
    assert site.prediction.predicted_value == 812.5
    assert site.prediction.status == "available"


async def test_summary_leaves_prediction_none_for_a_site_never_scored() -> None:
    service = PredictionService(
        sites=FauxDepotSites([FauxSite("A", "Site A")]),  # type: ignore[arg-type]
        predictions=FauxDepotPredictions([]),  # type: ignore[arg-type]
    )

    resume = await service.summary()

    assert resume.sites[0].prediction is None


async def test_summary_carries_an_insufficient_data_prediction_without_a_value() -> None:
    insuffisante = FauxPrediction(
        site_id="A",
        target_at=TARGET_AT,
        target_metric="consumption_kwh",
        period_minutes=60,
        predicted_value=None,
        status="insufficient_data",
        failure_reason="pas assez d'historique",
        model_reference="lightgbm-abc123",
        created_at=CREATED_AT,
    )
    service = PredictionService(
        sites=FauxDepotSites([FauxSite("A", "Site A")]),  # type: ignore[arg-type]
        predictions=FauxDepotPredictions([insuffisante]),  # type: ignore[arg-type]
    )

    resume = await service.summary()

    site = resume.sites[0]
    assert site.prediction is not None
    assert site.prediction.status == "insufficient_data"
    assert site.prediction.predicted_value is None
    assert site.prediction.failure_reason == "pas assez d'historique"


async def test_summary_covers_every_site_even_with_a_single_prediction_in_the_repository() -> None:
    service = PredictionService(
        sites=FauxDepotSites([FauxSite("A", "Site A"), FauxSite("B", "Site B")]),  # type: ignore[arg-type]
        predictions=FauxDepotPredictions([prediction_disponible("A")]),  # type: ignore[arg-type]
    )

    resume = await service.summary()

    par_site = {site.site_id: site for site in resume.sites}
    assert par_site["A"].prediction is not None
    assert par_site["B"].prediction is None
