from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_alert_service, get_current_principal
from app.core.principal import Principal
from app.core.roles import AccountKind, Role
from app.models.energy import Alert
from app.schemas.alert import AlertSeverity


def principal(role: Role = Role.LECTEUR) -> Principal:
    return Principal(
        id=uuid4(),
        email=f"{role.value}@enervision.fr",
        role=role,
        kind=AccountKind.HUMAIN,
        must_change_password=False,
    )


def alert(alert_id: int = 1, site_id: str = "site-1", severity: str = "high") -> Alert:
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


class FauxService:
    def __init__(self) -> None:
        self.alert = alert()
        self.appels: list[tuple[str | None, str | None]] = []

    async def list_all(
        self, *, site_id: str | None = None, severity: str | None = None
    ) -> list[Alert]:
        self.appels.append((site_id, severity))
        return [self.alert]


@pytest.fixture
def lecteur_connecte(app: FastAPI) -> Iterator[None]:
    app.dependency_overrides[get_current_principal] = lambda: principal()
    yield
    app.dependency_overrides.pop(get_current_principal, None)


@pytest.fixture
def servi(app: FastAPI, lecteur_connecte: None) -> Iterator[Callable[[], FauxService]]:
    def installe() -> FauxService:
        service = FauxService()
        app.dependency_overrides[get_alert_service] = lambda: service
        return service

    yield installe
    app.dependency_overrides.pop(get_alert_service, None)


async def test_list_alerts_returns_the_alerts(
    servi: Callable[[], FauxService], client: AsyncClient
) -> None:
    servi()

    response = await client.get("/api/v1/alerts")

    assert response.status_code == 200
    corps = response.json()
    assert corps == [
        {
            "alert_id": 1,
            "site_id": "site-1",
            "timestamp": "2026-09-16T00:00:00Z",
            "type": "threshold",
            "severity": "high",
            "message": "Dépassement du seuil configuré",
            "value": 812.5,
            "threshold": 720.0,
            "metric": "consumption_kw",
            "prediction_id": None,
        }
    ]


async def test_list_alerts_transmits_the_site_id_filter(
    servi: Callable[[], FauxService], client: AsyncClient
) -> None:
    service = servi()

    await client.get("/api/v1/alerts?site_id=site-1")

    assert service.appels == [("site-1", None)]


async def test_list_alerts_transmits_the_severity_filter(
    servi: Callable[[], FauxService], client: AsyncClient
) -> None:
    service = servi()

    await client.get("/api/v1/alerts?severity=critical")

    assert service.appels == [(None, AlertSeverity.CRITICAL)]


async def test_list_alerts_returns_422_for_an_unknown_severity(
    servi: Callable[[], FauxService], client: AsyncClient
) -> None:
    servi()

    response = await client.get("/api/v1/alerts?severity=invalide")

    assert response.status_code == 422


async def test_list_alerts_returns_an_empty_list_when_there_is_nothing(
    lecteur_connecte: None, fake_session: Callable[..., None], client: AsyncClient
) -> None:
    fake_session(result=[])

    response = await client.get("/api/v1/alerts")

    assert response.status_code == 200
    assert response.json() == []
