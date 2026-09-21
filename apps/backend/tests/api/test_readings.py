from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_current_principal, get_reading_service
from app.core.principal import Principal
from app.core.roles import AccountKind, Role
from app.models.energy import Reading
from app.services.reading import FenetreInverseeError, FenetreTropLargeError


def principal(role: Role = Role.LECTEUR) -> Principal:
    return Principal(
        id=uuid4(),
        email=f"{role.value}@enervision.fr",
        role=role,
        kind=AccountKind.HUMAIN,
        must_change_password=False,
    )


def reading(reading_id: int = 1, site_id: str = "site-1") -> Reading:
    return Reading(
        reading_id=reading_id,
        site_id=site_id,
        timestamp=datetime(2026, 9, 16, tzinfo=UTC),
        source="api_current",
        consumption_kw=42.5,
        consumption_kwh=None,
        consumption_euros=None,
        voltage_v=230.0,
        current_a=None,
        power_factor=None,
        temperature_celsius=None,
        humidity_percent=None,
        solar_irradiance_wm2=None,
        is_working_hours=True,
        data_quality="good",
        null_reasons=None,
        imputed_values=None,
        imputation_method=None,
        raw_data={},
    )


class FauxService:
    def __init__(self, leve: Exception | None = None) -> None:
        self.reading = reading()
        self.leve = leve
        self.appels: list[tuple[str | None, str | None, str | None, int, int]] = []

    async def list_history(
        self,
        *,
        site_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int,
        offset: int,
    ) -> list[Reading]:
        self.appels.append((site_id, start, end, limit, offset))
        if self.leve is not None:
            raise self.leve
        return [self.reading]


@pytest.fixture
def lecteur_connecte(app: FastAPI) -> Iterator[None]:
    app.dependency_overrides[get_current_principal] = lambda: principal()
    yield
    app.dependency_overrides.pop(get_current_principal, None)


@pytest.fixture
def servi(app: FastAPI, lecteur_connecte: None) -> Iterator[Callable[..., FauxService]]:
    def installe(*, leve: Exception | None = None) -> FauxService:
        service = FauxService(leve=leve)
        app.dependency_overrides[get_reading_service] = lambda: service
        return service

    yield installe
    app.dependency_overrides.pop(get_reading_service, None)


async def test_list_readings_returns_the_readings(
    servi: Callable[..., FauxService], client: AsyncClient
) -> None:
    servi()

    response = await client.get("/api/v1/readings")

    assert response.status_code == 200
    corps = response.json()
    assert corps == [
        {
            "reading_id": 1,
            "site_id": "site-1",
            "timestamp": "2026-09-16T00:00:00Z",
            "source": "api_current",
            "consumption_kw": 42.5,
            "consumption_kwh": None,
            "consumption_euros": None,
            "voltage_v": 230.0,
            "current_a": None,
            "power_factor": None,
            "temperature_celsius": None,
            "humidity_percent": None,
            "solar_irradiance_wm2": None,
            "is_working_hours": True,
            "data_quality": "good",
            "null_reasons": None,
            "imputed_values": None,
            "imputation_method": None,
        }
    ]


async def test_list_readings_transmits_the_filters_and_pagination(
    servi: Callable[..., FauxService], client: AsyncClient
) -> None:
    service = servi()

    response = await client.get(
        "/api/v1/readings",
        params={
            "site_id": "site-1",
            "start": "2026-09-01T00:00:00Z",
            "end": "2026-09-02T00:00:00Z",
            "limit": 50,
            "offset": 10,
        },
    )

    assert response.status_code == 200
    assert service.appels == [
        (
            "site-1",
            datetime(2026, 9, 1, tzinfo=UTC),
            datetime(2026, 9, 2, tzinfo=UTC),
            50,
            10,
        )
    ]


async def test_list_readings_returns_400_when_the_window_is_inverted(
    servi: Callable[..., FauxService], client: AsyncClient
) -> None:
    servi(leve=FenetreInverseeError())

    response = await client.get("/api/v1/readings")

    assert response.status_code == 400


async def test_list_readings_returns_400_when_the_window_is_too_large(
    servi: Callable[..., FauxService], client: AsyncClient
) -> None:
    servi(leve=FenetreTropLargeError())

    response = await client.get("/api/v1/readings")

    assert response.status_code == 400


async def test_list_readings_returns_422_for_a_limit_above_the_maximum(
    servi: Callable[..., FauxService], client: AsyncClient
) -> None:
    servi()

    response = await client.get("/api/v1/readings", params={"limit": 5000})

    assert response.status_code == 422


async def test_list_readings_returns_422_for_a_negative_offset(
    servi: Callable[..., FauxService], client: AsyncClient
) -> None:
    servi()

    response = await client.get("/api/v1/readings", params={"offset": -1})

    assert response.status_code == 422


async def test_list_readings_returns_an_empty_list_when_there_is_nothing(
    lecteur_connecte: None, fake_session: Callable[..., None], client: AsyncClient
) -> None:
    fake_session(result=[])

    response = await client.get("/api/v1/readings")

    assert response.status_code == 200
    assert response.json() == []
