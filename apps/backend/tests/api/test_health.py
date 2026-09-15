from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError

from app.db.session import get_session


async def test_liveness_exposes_service_metadata(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "EnerVision API",
        "version": "0.1.0",
        "environment": "local",
    }


async def test_readiness_reports_the_timescaledb_version(app: FastAPI, client: AsyncClient) -> None:
    class ReadySession:
        async def scalar(self, *_: object, **__: object) -> str:
            return "2.22.1"

    async def override() -> AsyncIterator[ReadySession]:
        yield ReadySession()

    app.dependency_overrides[get_session] = override

    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "reachable",
        "timescaledb": "2.22.1",
    }


async def test_readiness_returns_503_when_the_extension_is_missing(
    app: FastAPI, client: AsyncClient
) -> None:
    class SessionWithoutExtension:
        async def scalar(self, *_: object, **__: object) -> None:
            return None

    async def override() -> AsyncIterator[SessionWithoutExtension]:
        yield SessionWithoutExtension()

    app.dependency_overrides[get_session] = override

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
    app: FastAPI, client: AsyncClient, failure: Exception
) -> None:
    class UnreachableSession:
        async def scalar(self, *_: object, **__: object) -> None:
            raise failure

    async def override() -> AsyncIterator[UnreachableSession]:
        yield UnreachableSession()

    app.dependency_overrides[get_session] = override

    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "Base de donnees injoignable"


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
