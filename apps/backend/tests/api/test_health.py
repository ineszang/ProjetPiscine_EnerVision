from collections.abc import Callable

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError


async def test_liveness_exposes_service_metadata(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "EnerVision API",
        "version": "0.1.0",
        "environment": "local",
    }


async def test_readiness_reports_the_timescaledb_version(
    fake_session: Callable[..., None], client: AsyncClient
) -> None:
    fake_session(result="2.22.1")

    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "reachable",
        "timescaledb": "2.22.1",
    }


async def test_readiness_returns_503_when_the_extension_is_missing(
    fake_session: Callable[..., None], client: AsyncClient
) -> None:
    fake_session(result=None)

    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "Extension TimescaleDB absente"


@pytest.mark.parametrize(
    "failure",
    [
        OperationalError("SELECT 1", {}, Exception("connexion refusee")),
        ConnectionRefusedError(111, "Connection refused"),
    ],
    ids=["erreur_sqlalchemy", "erreur_reseau_asyncpg"],
)
async def test_readiness_returns_503_when_database_is_unreachable(
    fake_session: Callable[..., None], client: AsyncClient, failure: Exception
) -> None:
    fake_session(failure=failure)

    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "Base de données injoignable"


@pytest.mark.parametrize("path", ["/openapi.json", "/metrics"])
async def test_technical_endpoints_are_served(client: AsyncClient, path: str) -> None:
    assert (await client.get(path)).status_code == 200


@pytest.mark.integration
async def test_readiness_reaches_the_real_database(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ready"
    assert body["database"] == "reachable"
    assert body["timescaledb"]
