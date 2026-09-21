# Contrainte : la réponse de l'API Mock est une entrée hostile, pas une source de confiance.
# Voir OWASP API10 dans docs/architecture/owasp-traceabilite.md. Rien de ce qu'elle renvoie
# n'atteint la base sans passer par build_site_row() ou build_reading_row() : seuls les champs
# attendus sont recopiés, les grandeurs physiques sont bornées par PHYSICAL_BOUNDS et la taille
# des tableaux est plafonnée par MAX_SITES et par --limit. Une valeur hors bornes devient NULL
# et laisse sa trace dans null_reasons plutôt que de lever : le mock émet des anomalies par
# construction, et raw_data conserve de toute façon la réponse d'origine intacte.

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

MAX_SITES = 100

MAX_LIMIT = 1000

# Les quatre seules valeurs que la contrainte ck_reading_quality accepte.
ACCEPTED_QUALITIES = frozenset({"good", "partial", "degraded", "critical"})

PHYSICAL_BOUNDS: dict[str, tuple[float, float]] = {
    "consumption_kw": (0.0, 100_000.0),
    "consumption_kwh": (0.0, 100_000.0),
    "voltage_v": (0.0, 1_000.0),
    "current_a": (0.0, 10_000.0),
    "power_factor": (0.0, 1.0),
    "temperature_celsius": (-90.0, 60.0),
    "humidity_percent": (0.0, 100.0),
}

CAPACITY_BOUNDS = (0.0, 100_000.0)


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


def read_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)

    if not isinstance(value, str) or not value:
        raise ValueError(f"Champ {key} absent ou invalide dans la réponse de l'API Mock.")

    return value


def optional_text(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def coerce_measure(
    value: Any,
    bounds: tuple[float, float],
) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None

    lower, upper = bounds

    # Écarte aussi NaN et les infinis, qu'aucune comparaison de bornes ne retient.
    return float(value) if lower <= value <= upper else None


def resolve_quality(
    value: Any,
    rejected: list[str],
) -> str | None:
    quality = value if isinstance(value, str) and value in ACCEPTED_QUALITIES else None

    if rejected:
        return "critical" if quality == "critical" else "degraded"

    return quality


def resolve_null_reasons(
    value: Any,
    rejected: list[str],
) -> list[str]:
    reported = [str(reason) for reason in value] if isinstance(value, list) else []

    return reported + rejected


async def fetch_sites(
    client: httpx.AsyncClient,
) -> list[dict[str, Any]]:
    response = await client.get("/api/v1/sites")

    response.raise_for_status()

    payload = response.json()

    if not isinstance(payload, list):
        raise ValueError("La réponse /api/v1/sites doit être une liste.")

    if len(payload) > MAX_SITES:
        raise ValueError(f"La réponse /api/v1/sites dépasse le plafond de {MAX_SITES} sites.")

    return payload


def build_site_row(
    site: dict[str, Any],
) -> dict[str, Any]:
    return {
        "site_id": read_text(site, "site_id"),
        "site_type": read_text(site, "site_type"),
        "site_name": read_text(site, "site_name"),
        "location": optional_text(site.get("location")),
        "capacity_kw": coerce_measure(site.get("capacity_kw"), CAPACITY_BOUNDS),
        "status": optional_text(site.get("status")),
    }


async def upsert_sites(
    connection: AsyncConnection,
    sites: list[dict[str, Any]],
) -> None:
    rows = [build_site_row(site) for site in sites]

    if not rows:
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
        rows,
    )


async def fetch_readings(
    client: httpx.AsyncClient,
    site_id: str,
    start_time: datetime,
    end_time: datetime,
    limit: int = MAX_LIMIT,
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

    if len(payload) > limit:
        raise ValueError(f"La réponse /api/v1/readings dépasse la limite demandée de {limit}.")

    return payload


def build_reading_row(
    reading: dict[str, Any],
) -> dict[str, Any]:
    measures: dict[str, float | None] = {}
    rejected: list[str] = []

    for name, bounds in PHYSICAL_BOUNDS.items():
        received = reading.get(name)
        measures[name] = coerce_measure(received, bounds)

        if received is not None and measures[name] is None:
            rejected.append(f"out_of_physical_bounds:{name}")

    return {
        "site_id": read_text(reading, "site_id"),
        "timestamp": parse_datetime(read_text(reading, "timestamp")),
        "source": SOURCE_HISTORY,
        "dataset_id": None,
        **measures,
        "consumption_euros": None,
        "solar_irradiance_wm2": None,
        "is_working_hours": None,
        "data_quality": resolve_quality(reading.get("data_quality"), rejected),
        "null_reasons": resolve_null_reasons(reading.get("null_reasons"), rejected),
        "imputed_values": None,
        "imputation_method": None,
        "raw_data": json.dumps(
            reading,
            ensure_ascii=False,
        ),
    }


# Le conflit vise l'index unique uq_reading_source plutôt que la table entière : sans cible
# nommée, DO NOTHING avalerait aussi une violation de clé primaire.
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
    ON CONFLICT (site_id, timestamp, source, (coalesce(dataset_id, 0)))
    DO NOTHING
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
            site_id = read_text(site, "site_id")

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
        default=MAX_LIMIT,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.limit < 1 or args.limit > MAX_LIMIT:
        raise ValueError(f"--limit doit être compris entre 1 et {MAX_LIMIT}.")

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
