import json
from datetime import datetime
from typing import Any

import httpx
import pytest
from httpx import AsyncClient, MockTransport, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.etl.mock_api_import import (
    READING_INSERT,
    SOURCE_HISTORY,
    build_reading_batch,
    build_reading_row,
    fetch_readings,
    fetch_sites,
)


def make_site() -> dict[str, Any]:
    return {
        "site_id": "SITE001",
        "site_type": "office",
        "site_name": "Bureau Paris La Défense",
        "location": "Paris, France",
        "capacity_kw": 200,
        "status": "active",
    }


def make_reading() -> dict[str, Any]:
    return {
        "timestamp": "2024-06-15T12:00:00Z",
        "site_id": "SITE001",
        "site_type": "office",
        "consumption_kw": 87.34,
        "consumption_kwh": 87.34,
        "voltage_v": 401.2,
        "current_a": 132.5,
        "power_factor": 0.923,
        "temperature_celsius": 22.1,
        "humidity_percent": 58.4,
        "null_reasons": [],
        "data_quality": "good",
    }


async def test_fetch_sites_returns_sites() -> None:
    def handler(request: Request) -> Response:
        assert request.url.path == "/api/v1/sites"
        return Response(
            status_code=200,
            json=[make_site()],
        )

    transport = MockTransport(handler)

    async with AsyncClient(
        transport=transport,
        base_url="https://mock.test",
    ) as client:
        sites = await fetch_sites(client)

    assert len(sites) == 1
    assert sites[0]["site_id"] == "SITE001"
    assert sites[0]["site_type"] == "office"


async def test_fetch_readings_sends_expected_query_parameters() -> None:
    captured_params: dict[str, str] = {}

    def handler(request: Request) -> Response:
        nonlocal captured_params

        captured_params = dict(request.url.params)

        return Response(
            status_code=200,
            json=[make_reading()],
        )

    transport = MockTransport(handler)

    start_time = datetime.fromisoformat("2024-06-15T12:00:00")
    end_time = datetime.fromisoformat("2024-06-15T13:00:00")

    async with AsyncClient(
        transport=transport,
        base_url="https://mock.test",
    ) as client:
        readings = await fetch_readings(
            client=client,
            site_id="SITE001",
            start_time=start_time,
            end_time=end_time,
            limit=60,
        )

    assert len(readings) == 1
    assert captured_params["site_id"] == "SITE001"
    assert captured_params["start_time"] == "2024-06-15T12:00:00"
    assert captured_params["end_time"] == "2024-06-15T13:00:00"
    assert captured_params["limit"] == "60"


async def test_fetch_readings_rejects_non_list_response() -> None:
    def handler(request: Request) -> Response:
        return Response(
            status_code=200,
            json={"unexpected": "payload"},
        )

    transport = MockTransport(handler)

    async with AsyncClient(
        transport=transport,
        base_url="https://mock.test",
    ) as client:
        with pytest.raises(
            ValueError,
            match="La réponse /api/v1/readings doit être une liste",
        ):
            await fetch_readings(
                client=client,
                site_id="SITE001",
                start_time=datetime.fromisoformat("2024-06-15T12:00:00"),
                end_time=datetime.fromisoformat("2024-06-15T13:00:00"),
                limit=60,
            )


async def test_fetch_readings_raises_on_http_error() -> None:
    def handler(request: Request) -> Response:
        return Response(
            status_code=404,
            json={"detail": "Site non trouvé"},
        )

    transport = MockTransport(handler)

    async with AsyncClient(
        transport=transport,
        base_url="https://mock.test",
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_readings(
                client=client,
                site_id="SITE999",
                start_time=datetime.fromisoformat("2024-06-15T12:00:00"),
                end_time=datetime.fromisoformat("2024-06-15T13:00:00"),
                limit=60,
            )


def test_build_reading_row_respects_database_contract() -> None:
    reading = make_reading()

    row = build_reading_row(reading)

    assert row["site_id"] == "SITE001"
    assert row["source"] == SOURCE_HISTORY
    assert row["source"] == "api_history"
    assert row["dataset_id"] is None

    assert row["timestamp"] == datetime.fromisoformat("2024-06-15T12:00:00+00:00")

    assert row["consumption_kw"] == 87.34
    assert row["consumption_kwh"] == 87.34
    assert row["data_quality"] == "good"
    assert row["null_reasons"] == []

    assert row["imputed_values"] is None
    assert row["imputation_method"] is None


def test_build_reading_row_keeps_null_values_and_quality() -> None:
    reading = make_reading()

    reading["consumption_kw"] = None
    reading["consumption_kwh"] = None
    reading["voltage_v"] = None
    reading["current_a"] = None
    reading["power_factor"] = None
    reading["data_quality"] = "degraded"
    reading["null_reasons"] = [
        "consumption_sensor_failure",
        "electrical_sensor_failure",
    ]

    row = build_reading_row(reading)

    assert row["consumption_kw"] is None
    assert row["consumption_kwh"] is None
    assert row["voltage_v"] is None
    assert row["current_a"] is None
    assert row["power_factor"] is None

    assert row["data_quality"] == "degraded"
    assert row["null_reasons"] == [
        "consumption_sensor_failure",
        "electrical_sensor_failure",
    ]

    assert row["imputed_values"] is None
    assert row["imputation_method"] is None


def test_build_reading_row_keeps_raw_source_data() -> None:
    reading = make_reading()

    row = build_reading_row(reading)

    raw_data = json.loads(row["raw_data"])

    assert raw_data == reading


def test_build_reading_batch_transforms_all_readings() -> None:
    first = make_reading()

    second = make_reading()
    second["timestamp"] = "2024-06-15T12:01:00Z"
    second["consumption_kw"] = 90.5

    rows = build_reading_batch([first, second])

    assert len(rows) == 2

    assert rows[0]["site_id"] == "SITE001"
    assert rows[0]["consumption_kw"] == 87.34

    assert rows[1]["site_id"] == "SITE001"
    assert rows[1]["consumption_kw"] == 90.5


@pytest.mark.integration
async def test_reading_insert_is_idempotent(
    session: AsyncSession,
) -> None:
    reading = make_reading()
    row = build_reading_row(reading)

    await session.execute(
        text(
            """
            INSERT INTO site (
                site_id,
                site_type,
                site_name,
                location,
                capacity_kw,
                status
            )
            VALUES (
                :site_id,
                :site_type,
                :site_name,
                :location,
                :capacity_kw,
                :status
            )
            ON CONFLICT (site_id)
            DO UPDATE SET
                site_type = EXCLUDED.site_type,
                site_name = EXCLUDED.site_name,
                location = EXCLUDED.location,
                capacity_kw = EXCLUDED.capacity_kw,
                status = EXCLUDED.status
            """
        ),
        make_site(),
    )

    await session.execute(
        READING_INSERT,
        [row],
    )

    await session.execute(
        READING_INSERT,
        [row],
    )

    result = await session.execute(
        text(
            """
            SELECT COUNT(*)
            FROM reading
            WHERE site_id = :site_id
              AND timestamp = :timestamp
              AND source = :source
            """
        ),
        {
            "site_id": row["site_id"],
            "timestamp": row["timestamp"],
            "source": row["source"],
        },
    )

    assert result.scalar_one() == 1

    await session.rollback()
