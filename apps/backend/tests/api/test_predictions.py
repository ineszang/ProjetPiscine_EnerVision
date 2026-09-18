from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_current_principal, get_prediction_service
from app.core.principal import Principal
from app.core.roles import AccountKind, Role
from app.services.prediction import PredictionSummary, SitePrediction, SitePredictionSummary

TARGET_AT = datetime(2026, 9, 16, 13, 0, tzinfo=UTC)
CREATED_AT = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


def principal(role: Role = Role.LECTEUR) -> Principal:
    return Principal(
        id=uuid4(),
        email=f"{role.value}@enervision.fr",
        role=role,
        kind=AccountKind.HUMAIN,
        must_change_password=False,
    )


class FauxService:
    def __init__(self) -> None:
        self.resume = PredictionSummary(
            timestamp=datetime.now(UTC),
            sites=[
                SitePredictionSummary(
                    site_id="SITE001",
                    site_name="Bureau Paris La Défense",
                    prediction=SitePrediction(
                        target_at=TARGET_AT,
                        target_metric="consumption_kwh",
                        period_minutes=60,
                        predicted_value=812.5,
                        status="available",
                        failure_reason=None,
                        model_reference="lightgbm-abc123",
                        created_at=CREATED_AT,
                    ),
                ),
                SitePredictionSummary(site_id="SITE002", site_name="Usine Lyon", prediction=None),
            ],
        )

    async def summary(self) -> PredictionSummary:
        return self.resume


@pytest.fixture
def servi(app: FastAPI) -> Iterator[Callable[[], FauxService]]:
    def installe() -> FauxService:
        service = FauxService()
        app.dependency_overrides[get_prediction_service] = lambda: service
        app.dependency_overrides[get_current_principal] = lambda: principal()
        return service

    yield installe
    app.dependency_overrides.pop(get_prediction_service, None)
    app.dependency_overrides.pop(get_current_principal, None)


async def test_get_predictions_returns_the_service_result(
    servi: Callable[[], FauxService], client: AsyncClient
) -> None:
    servi()

    response = await client.get("/api/v1/predictions")

    assert response.status_code == 200
    corps = response.json()
    premier, second = corps["sites"]
    assert premier["site_id"] == "SITE001"
    assert premier["prediction"]["predicted_value"] == 812.5
    assert premier["prediction"]["status"] == "available"
    assert second["site_id"] == "SITE002"
    assert second["prediction"] is None
