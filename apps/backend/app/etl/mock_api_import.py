from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.core.config import get_settings

SOURCE_HISTORY = "api_history"


def create_mock_api_client() -> httpx.AsyncClient:
    settings = get_settings()

    if settings.mock_api_username is None or settings.mock_api_password is None:
        raise ValueError("Les identifiants de l'API Mock ne sont pas configurés.")

    return httpx.AsyncClient(
        base_url=settings.mock_api_base_url.rstrip("/"),
        auth=(
            settings.mock_api_username,
            settings.mock_api_password.get_secret_value(),
        ),
        timeout=settings.mock_api_timeout_seconds,
    )


async def fetch_sites(
    client: httpx.AsyncClient,
) -> list[dict[str, Any]]:
    response = await client.get("/api/v1/sites")

    response.raise_for_status()

    payload = response.json()

    if not isinstance(payload, list):
        raise ValueError("La réponse /api/v1/sites doit être une liste.")

    return payload


async def upsert_sites(
    connection: AsyncConnection,
    sites: list[dict[str, Any]],
) -> None:
    if not sites:
        return

    await connection.execute(
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
        sites,
    )


async def fetch_readings(
    client: httpx.AsyncClient,
    site_id: str,
    start_time: datetime,
    end_time: datetime,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    response = await client.get(
        "/api/v1/readings",
        params={
            "site_id": site_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "limit": limit,
        },
    )

    response.raise_for_status()

    payload = response.json()

    if not isinstance(payload, list):
        raise ValueError("La réponse /api/v1/readings doit être une liste.")

    return payload


def build_reading_row(
    reading: dict[str, Any],
) -> dict[str, Any]:
    timestamp = datetime.fromisoformat(reading["timestamp"].replace("Z", "+00:00"))
    return {
        "site_id": reading["site_id"],
        "timestamp": timestamp,
        "source": SOURCE_HISTORY,
        "dataset_id": None,
        "consumption_kw": reading.get("consumption_kw"),
        "consumption_kwh": reading.get("consumption_kwh"),
        "consumption_euros": None,
        "voltage_v": reading.get("voltage_v"),
        "current_a": reading.get("current_a"),
        "power_factor": reading.get("power_factor"),
        "temperature_celsius": reading.get("temperature_celsius"),
        "humidity_percent": reading.get("humidity_percent"),
        "solar_irradiance_wm2": None,
        "is_working_hours": None,
        "data_quality": reading.get("data_quality"),
        "null_reasons": reading.get("null_reasons"),
        "imputed_values": None,
        "imputation_method": None,
        "raw_data": json.dumps(
            reading,
            ensure_ascii=False,
        ),
    }


READING_INSERT = text(
    """
    INSERT INTO reading (
        site_id,
        timestamp,
        source,
        dataset_id,
        consumption_kw,
        consumption_kwh,
        consumption_euros,
        voltage_v,
        current_a,
        power_factor,
        temperature_celsius,
        humidity_percent,
        solar_irradiance_wm2,
        is_working_hours,
        data_quality,
        null_reasons,
        imputed_values,
        imputation_method,
        raw_data
    )
    VALUES (
        :site_id,
        :timestamp,
        :source,
        :dataset_id,
        :consumption_kw,
        :consumption_kwh,
        :consumption_euros,
        :voltage_v,
        :current_a,
        :power_factor,
        :temperature_celsius,
        :humidity_percent,
        :solar_irradiance_wm2,
        :is_working_hours,
        :data_quality,
        :null_reasons,
        CAST(:imputed_values AS jsonb),
        :imputation_method,
        CAST(:raw_data AS jsonb)
    )
    ON CONFLICT DO NOTHING
    """
)


def build_reading_batch(
    readings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [build_reading_row(reading) for reading in readings]


async def import_mock_api_history(
    start_time: datetime,
    end_time: datetime,
    limit: int,
    dry_run: bool,
) -> None:
    settings = get_settings()

    async with create_mock_api_client() as client:
        sites = await fetch_sites(client)

        print(f"Sites récupérés : {len(sites)}")

        all_readings: list[dict[str, Any]] = []

        for site in sites:
            site_id = site["site_id"]

            readings = await fetch_readings(
                client=client,
                site_id=site_id,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
            )

            print(f"{site_id}: {len(readings)} lectures")

            all_readings.extend(readings)

    print(f"Lectures récupérées : {len(all_readings)}")

    if dry_run:
        print("Dry-run terminé : aucune donnée écrite.")
        return

    engine = create_async_engine(
        str(settings.database_url),
        pool_pre_ping=True,
    )

    try:
        async with engine.begin() as connection:
            await upsert_sites(
                connection,
                sites,
            )

            rows = build_reading_batch(all_readings)

            if rows:
                await connection.execute(
                    READING_INSERT,
                    rows,
                )

    finally:
        await engine.dispose()

    print("Import API Mock terminé.")


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=("Import historique depuis l'API Mock EnerVision"))

    parser.add_argument(
        "--start-time",
        required=True,
        type=parse_datetime,
    )

    parser.add_argument(
        "--end-time",
        required=True,
        type=parse_datetime,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.limit < 1 or args.limit > 1000:
        raise ValueError("--limit doit être compris entre 1 et 1000.")

    if args.start_time >= args.end_time:
        raise ValueError("--start-time doit être antérieur à --end-time.")

    asyncio.run(
        import_mock_api_history(
            start_time=args.start_time,
            end_time=args.end_time,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
