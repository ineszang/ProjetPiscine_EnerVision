from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_current_principal, get_sensor_service
from app.core.principal import Principal
from app.core.roles import AccountKind, Role
from app.services.sensor import DiagnosticCapteur, EtatCapteurs, SanteCapteurs, SanteSite

TIMESTAMP = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


def principal(role: Role = Role.ADMIN) -> Principal:
    return Principal(
        id=uuid4(),
        email=f"{role.value}@enervision.fr",
        role=role,
        kind=AccountKind.HUMAIN,
        must_change_password=False,
    )


class FauxService:
    def __init__(self) -> None:
        ok = DiagnosticCapteur(status="ok", since=None)
        en_echec = DiagnosticCapteur(status="failing", since=TIMESTAMP)
        self.etat = EtatCapteurs(
            timestamp=TIMESTAMP,
            sites=[
                SanteSite(
                    site_id="SITE001",
                    site_name="Bureau Paris La Défense",
                    sensors=SanteCapteurs(
                        consumption=ok,
                        electrical=ok,
                        temperature=en_echec,
                        humidity=ok,
                        network=ok,
                    ),
                    overall="degraded",
                )
            ],
        )

    async def status(self) -> EtatCapteurs:
        return self.etat


@pytest.fixture
def admin_connecte(app: FastAPI) -> Iterator[None]:
    app.dependency_overrides[get_current_principal] = lambda: principal()
    yield
    app.dependency_overrides.pop(get_current_principal, None)


@pytest.fixture
def servi(app: FastAPI, admin_connecte: None) -> Iterator[Callable[[], FauxService]]:
    def installe() -> FauxService:
        service = FauxService()
        app.dependency_overrides[get_sensor_service] = lambda: service
        return service

    yield installe
    app.dependency_overrides.pop(get_sensor_service, None)


async def test_get_status_returns_the_service_result(
    servi: Callable[[], FauxService], client: AsyncClient
) -> None:
    servi()

    response = await client.get("/api/v1/sensors/status")

    assert response.status_code == 200
    corps = response.json()
    assert corps["sites"][0]["site_id"] == "SITE001"
    assert corps["sites"][0]["overall"] == "degraded"
    assert corps["sites"][0]["sensors"]["temperature"]["status"] == "failing"
    assert corps["sites"][0]["sensors"]["consumption"]["status"] == "ok"


async def test_get_status_refuses_a_reader(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_current_principal] = lambda: principal(Role.LECTEUR)

    response = await client.get("/api/v1/sensors/status")

    assert response.status_code == 403
