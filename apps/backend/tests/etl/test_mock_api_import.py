import json
import sys
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import AsyncClient, MockTransport, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import app.etl.mock_api_import as mock_api_import
from app.etl.mock_api_import import (
    MAX_SITES,
    READING_INSERT,
    SOURCE_HISTORY,
    build_reading_batch,
    build_reading_row,
    build_site_row,
    fetch_readings,
    fetch_sites,
    upsert_sites,
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


async def test_fetch_sites_rejects_non_list_response() -> None:
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
            match="La réponse /api/v1/sites doit être une liste",
        ):
            await fetch_sites(client)


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


def test_create_mock_api_client_requires_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        mock_api_username=None,
        mock_api_password=None,
    )

    monkeypatch.setattr(
        mock_api_import,
        "get_settings",
        lambda: settings,
    )

    with pytest.raises(
        ValueError,
        match="Les identifiants de l'API Mock ne sont pas configurés",
    ):
        mock_api_import.create_mock_api_client()


@pytest.mark.parametrize(
    ("username", "password_value"),
    [
        ("", "test-password"),
        ("test-user", ""),
        ("   ", "test-password"),
        ("test-user", "   "),
    ],
)
def test_create_mock_api_client_rejects_empty_credentials(
    monkeypatch: pytest.MonkeyPatch,
    username: str,
    password_value: str,
) -> None:
    password = MagicMock()
    password.get_secret_value.return_value = password_value

    settings = SimpleNamespace(
        mock_api_username=username,
        mock_api_password=password,
    )

    monkeypatch.setattr(
        mock_api_import,
        "get_settings",
        lambda: settings,
    )

    with pytest.raises(
        ValueError,
        match="Les identifiants de l'API Mock ne sont pas configurés",
    ):
        mock_api_import.create_mock_api_client()


async def test_create_mock_api_client_uses_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    password = MagicMock()
    password.get_secret_value.return_value = "test-password"

    settings = SimpleNamespace(
        mock_api_base_url="https://mock.test/",
        mock_api_username="test-user",
        mock_api_password=password,
        mock_api_timeout_seconds=10.0,
    )

    monkeypatch.setattr(
        mock_api_import,
        "get_settings",
        lambda: settings,
    )

    client = mock_api_import.create_mock_api_client()

    try:
        assert str(client.base_url) == "https://mock.test"
        assert client.timeout.connect == 10.0
    finally:
        await client.aclose()


async def test_upsert_sites_with_empty_list_does_nothing() -> None:
    connection = AsyncMock()

    await upsert_sites(
        connection,
        [],
    )

    connection.execute.assert_not_awaited()


async def test_import_mock_api_history_dry_run_does_not_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: Request) -> Response:
        if request.url.path == "/api/v1/sites":
            return Response(
                status_code=200,
                json=[make_site()],
            )

        if request.url.path == "/api/v1/readings":
            return Response(
                status_code=200,
                json=[make_reading()],
            )

        return Response(status_code=404)

    transport = MockTransport(handler)

    client = AsyncClient(
        transport=transport,
        base_url="https://mock.test",
    )

    monkeypatch.setattr(
        mock_api_import,
        "create_mock_api_client",
        lambda: client,
    )

    monkeypatch.setattr(
        mock_api_import,
        "get_settings",
        lambda: SimpleNamespace(
            database_url="postgresql+asyncpg://unused",
        ),
    )

    create_engine_mock = MagicMock()

    monkeypatch.setattr(
        mock_api_import,
        "create_async_engine",
        create_engine_mock,
    )

    await mock_api_import.import_mock_api_history(
        start_time=datetime.fromisoformat("2024-06-15T12:00:00"),
        end_time=datetime.fromisoformat("2024-06-15T13:00:00"),
        limit=60,
        dry_run=True,
    )

    create_engine_mock.assert_not_called()


async def test_import_mock_api_history_loads_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: Request) -> Response:
        if request.url.path == "/api/v1/sites":
            return Response(
                status_code=200,
                json=[make_site()],
            )

        if request.url.path == "/api/v1/readings":
            return Response(
                status_code=200,
                json=[make_reading()],
            )

        return Response(status_code=404)

    transport = MockTransport(handler)

    client = AsyncClient(
        transport=transport,
        base_url="https://mock.test",
    )

    monkeypatch.setattr(
        mock_api_import,
        "create_mock_api_client",
        lambda: client,
    )

    monkeypatch.setattr(
        mock_api_import,
        "get_settings",
        lambda: SimpleNamespace(
            database_url="postgresql+asyncpg://test:test@localhost/test",
        ),
    )

    connection = AsyncMock()

    transaction_context = MagicMock()
    transaction_context.__aenter__ = AsyncMock(
        return_value=connection,
    )
    transaction_context.__aexit__ = AsyncMock(
        return_value=None,
    )

    engine = MagicMock()
    engine.begin.return_value = transaction_context
    engine.dispose = AsyncMock()

    create_engine_mock = MagicMock(
        return_value=engine,
    )

    upsert_sites_mock = AsyncMock()

    monkeypatch.setattr(
        mock_api_import,
        "create_async_engine",
        create_engine_mock,
    )

    monkeypatch.setattr(
        mock_api_import,
        "upsert_sites",
        upsert_sites_mock,
    )

    await mock_api_import.import_mock_api_history(
        start_time=datetime.fromisoformat("2024-06-15T12:00:00"),
        end_time=datetime.fromisoformat("2024-06-15T13:00:00"),
        limit=60,
        dry_run=False,
    )

    create_engine_mock.assert_called_once_with(
        "postgresql+asyncpg://test:test@localhost/test",
        pool_pre_ping=True,
    )

    upsert_sites_mock.assert_awaited_once_with(
        connection,
        [make_site()],
    )

    connection.execute.assert_awaited_once()
    engine.dispose.assert_awaited_once()


def test_parse_datetime_accepts_z_suffix() -> None:
    result = mock_api_import.parse_datetime(
        "2024-06-15T12:00:00Z",
    )

    assert result == datetime.fromisoformat(
        "2024-06-15T12:00:00+00:00",
    )


def test_parse_args_reads_cli_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mock_api_import",
            "--start-time",
            "2024-06-15T12:00:00Z",
            "--end-time",
            "2024-06-15T13:00:00Z",
            "--limit",
            "60",
            "--dry-run",
        ],
    )

    args = mock_api_import.parse_args()

    assert args.start_time == datetime.fromisoformat(
        "2024-06-15T12:00:00+00:00",
    )
    assert args.end_time == datetime.fromisoformat(
        "2024-06-15T13:00:00+00:00",
    )
    assert args.limit == 60
    assert args.dry_run is True


def test_main_rejects_limit_out_of_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mock_api_import",
            "--start-time",
            "2024-06-15T12:00:00Z",
            "--end-time",
            "2024-06-15T13:00:00Z",
            "--limit",
            "0",
        ],
    )

    with pytest.raises(
        ValueError,
        match="--limit doit être compris entre 1 et 1000",
    ):
        mock_api_import.main()


def test_main_rejects_invalid_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mock_api_import",
            "--start-time",
            "2024-06-15T14:00:00Z",
            "--end-time",
            "2024-06-15T13:00:00Z",
            "--limit",
            "60",
        ],
    )

    with pytest.raises(
        ValueError,
        match="--start-time doit être antérieur à --end-time",
    ):
        mock_api_import.main()


def test_main_runs_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start_time = datetime.fromisoformat(
        "2024-06-15T12:00:00+00:00",
    )
    end_time = datetime.fromisoformat(
        "2024-06-15T13:00:00+00:00",
    )

    import_mock = AsyncMock()

    monkeypatch.setattr(
        mock_api_import,
        "parse_args",
        lambda: SimpleNamespace(
            start_time=start_time,
            end_time=end_time,
            limit=60,
            dry_run=True,
        ),
    )

    monkeypatch.setattr(
        mock_api_import,
        "import_mock_api_history",
        import_mock,
    )

    mock_api_import.main()

    import_mock.assert_awaited_once_with(
        start_time=start_time,
        end_time=end_time,
        limit=60,
        dry_run=True,
    )


async def test_fetch_sites_rejects_a_response_above_the_cap() -> None:
    def handler(request: Request) -> Response:
        return Response(
            status_code=200,
            json=[make_site() for _ in range(MAX_SITES + 1)],
        )

    transport = MockTransport(handler)

    async with AsyncClient(
        transport=transport,
        base_url="https://mock.test",
    ) as client:
        with pytest.raises(
            ValueError,
            match=f"dépasse le plafond de {MAX_SITES} sites",
        ):
            await fetch_sites(client)


async def test_fetch_readings_rejects_a_response_above_the_requested_limit() -> None:
    def handler(request: Request) -> Response:
        return Response(
            status_code=200,
            json=[make_reading(), make_reading(), make_reading()],
        )

    transport = MockTransport(handler)

    async with AsyncClient(
        transport=transport,
        base_url="https://mock.test",
    ) as client:
        with pytest.raises(
            ValueError,
            match="dépasse la limite demandée de 2",
        ):
            await fetch_readings(
                client=client,
                site_id="SITE001",
                start_time=datetime.fromisoformat("2024-06-15T12:00:00"),
                end_time=datetime.fromisoformat("2024-06-15T13:00:00"),
                limit=2,
            )


def test_build_reading_row_neutralises_values_outside_physical_bounds() -> None:
    reading = make_reading()

    reading["power_factor"] = 42.0
    reading["temperature_celsius"] = 1e30
    reading["humidity_percent"] = -1.0

    row = build_reading_row(reading)

    assert row["power_factor"] is None
    assert row["temperature_celsius"] is None
    assert row["humidity_percent"] is None

    assert row["null_reasons"] == [
        "out_of_physical_bounds:power_factor",
        "out_of_physical_bounds:temperature_celsius",
        "out_of_physical_bounds:humidity_percent",
    ]

    assert row["data_quality"] == "degraded"

    assert json.loads(row["raw_data"])["power_factor"] == 42.0


def test_build_reading_row_rejects_a_measure_that_is_not_a_number() -> None:
    reading = make_reading()

    reading["consumption_kw"] = "87.34"

    row = build_reading_row(reading)

    assert row["consumption_kw"] is None
    assert "out_of_physical_bounds:consumption_kw" in row["null_reasons"]


def test_build_reading_row_drops_a_quality_the_database_refuses() -> None:
    reading = make_reading()

    reading["data_quality"] = "unknown"

    row = build_reading_row(reading)

    assert row["data_quality"] is None


def test_build_reading_row_requires_an_identifier() -> None:
    reading = make_reading()

    del reading["site_id"]

    with pytest.raises(
        ValueError,
        match="Champ site_id absent ou invalide",
    ):
        build_reading_row(reading)


def test_build_site_row_keeps_only_the_expected_columns() -> None:
    site = make_site()

    site["unexpected"] = "valeur hostile"
    site["capacity_kw"] = -5.0
    site["status"] = 12

    row = build_site_row(site)

    assert set(row) == {
        "site_id",
        "site_type",
        "site_name",
        "location",
        "capacity_kw",
        "status",
    }

    assert row["capacity_kw"] is None
    assert row["status"] is None


async def test_upsert_sites_sends_only_the_expected_columns() -> None:
    connection = AsyncMock()

    site = make_site()
    site["unexpected"] = "valeur hostile"

    await upsert_sites(
        connection,
        [site],
    )

    rows = connection.execute.await_args.args[1]

    assert "unexpected" not in rows[0]
    assert rows[0]["site_id"] == "SITE001"


@pytest.mark.integration
async def test_reading_insert_is_idempotent(
    session: AsyncSession,
) -> None:
    reading = make_reading()
    row = build_reading_row(reading)

    connection = await session.connection()

    await upsert_sites(
        connection,
        [make_site()],
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


@pytest.mark.integration
async def test_out_of_bounds_reading_is_stored_neutralised(
    session: AsyncSession,
) -> None:
    reading = make_reading()
    reading["power_factor"] = 42.0

    row = build_reading_row(reading)

    connection = await session.connection()

    await upsert_sites(
        connection,
        [make_site()],
    )

    await session.execute(
        READING_INSERT,
        [row],
    )

    result = await session.execute(
        text(
            """
            SELECT power_factor, data_quality, null_reasons, raw_data ->> 'power_factor'
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

    stored = result.one()

    await session.rollback()

    assert stored[0] is None
    assert stored[1] == "degraded"
    assert stored[2] == ["out_of_physical_bounds:power_factor"]
    assert stored[3] == "42.0"
