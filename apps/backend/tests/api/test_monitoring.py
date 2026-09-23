from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_current_principal, get_drift_service
from app.core.principal import Principal
from app.core.roles import AccountKind, Role
from app.models.energy import DriftReport

INSTANT = datetime(2026, 9, 22, 12, tzinfo=UTC)


def operateur() -> Principal:
    return Principal(
        id=uuid4(),
        email="operateur@enervision.fr",
        role=Role.OPERATEUR,
        kind=AccountKind.HUMAIN,
        must_change_password=False,
    )


def rapport(*, site_id: str | None) -> DriftReport:
    return DriftReport(
        drift_report_id=1,
        computed_at=INSTANT,
        site_id=site_id,
        window_start=INSTANT - timedelta(hours=168),
        window_end=INSTANT,
        reference_start=None,
        reference_end=None,
        n_observations=48,
        mae=1.5,
        mape=12.0,
        bias=0.3,
        reference_mae=1.2,
        coverage_ratio=0.95,
        insufficient_data_ratio=0.0,
        model_references=["lightgbm-aaa"],
        status="stable",
        reason=None,
    )


class FauxService:
    def __init__(self, rapports: Sequence[DriftReport]) -> None:
        self.rapports = list(rapports)
        self.site_demande: str | None = None

    async def derniers(self, *, site_id: str | None = None) -> Sequence[DriftReport]:
        self.site_demande = site_id
        return self.rapports


@pytest.fixture
def servi(app: FastAPI) -> Iterator[list[DriftReport]]:
    rapports = [rapport(site_id="SITE001"), rapport(site_id=None)]
    service = FauxService(rapports)
    app.dependency_overrides[get_current_principal] = operateur
    app.dependency_overrides[get_drift_service] = lambda: service
    yield rapports
    app.dependency_overrides.clear()


async def test_drift_returns_the_latest_report_of_every_site(
    servi: list[DriftReport], client: AsyncClient
) -> None:
    reponse = await client.get("/api/v1/monitoring/drift")

    assert reponse.status_code == 200
    assert [ligne["site_id"] for ligne in reponse.json()] == ["SITE001", None]


async def test_drift_exposes_the_metrics_of_the_stored_report(
    servi: list[DriftReport], client: AsyncClient
) -> None:
    reponse = await client.get("/api/v1/monitoring/drift")

    premier = reponse.json()[0]
    assert premier["status"] == "stable"
    assert premier["mae"] == 1.5
    assert premier["model_references"] == ["lightgbm-aaa"]


async def test_drift_returns_an_empty_list_when_no_report_exists(
    app: FastAPI, client: AsyncClient
) -> None:
    app.dependency_overrides[get_current_principal] = operateur
    app.dependency_overrides[get_drift_service] = lambda: FauxService([])

    reponse = await client.get("/api/v1/monitoring/drift")

    assert reponse.status_code == 200
    assert reponse.json() == []
    app.dependency_overrides.clear()
