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
        async def execute(self, *_: object, **__: object) -> None:
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
