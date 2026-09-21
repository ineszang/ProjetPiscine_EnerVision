from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_current_principal, get_stats_service
from app.core.principal import Principal
from app.core.roles import AccountKind, Role
from app.services.stats import ConsumptionSummary, SiteConsumption


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
        self.resume = ConsumptionSummary(
            timestamp=datetime.now(UTC),
            total_sites=1,
            total_consumption_kw=87.34,
            total_capacity_kw=200,
            average_load_percent=43.7,
            sites=[
                SiteConsumption(
                    site_id="SITE001",
                    site_name="Bureau Paris La Défense",
                    current_consumption_kw=87.34,
                    capacity_kw=200,
                    load_percent=43.7,
                    data_quality="good",
                )
            ],
        )

    async def summary(self) -> ConsumptionSummary:
        return self.resume


@pytest.fixture
def servi(app: FastAPI) -> Iterator[Callable[[], FauxService]]:
    def installe() -> FauxService:
        service = FauxService()
        app.dependency_overrides[get_stats_service] = lambda: service
        app.dependency_overrides[get_current_principal] = lambda: principal()
        return service

    yield installe
    app.dependency_overrides.pop(get_stats_service, None)
    app.dependency_overrides.pop(get_current_principal, None)


async def test_get_summary_returns_the_service_result(
    servi: Callable[[], FauxService], client: AsyncClient
) -> None:
    servi()

    response = await client.get("/api/v1/stats/summary")

    assert response.status_code == 200
    corps = response.json()
    assert corps["total_sites"] == 1
    assert corps["sites"][0]["site_id"] == "SITE001"
    assert corps["sites"][0]["data_quality"] == "good"
