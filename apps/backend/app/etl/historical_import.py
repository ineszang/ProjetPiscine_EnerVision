from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.core.config import get_settings

REQUIRED_COLUMNS = {
    "timestamp",
    "site_id",
    "site_type",
    "site_name",
    "consumption_kwh",
    "consumption_euros",
    "temperature_celsius",
    "humidity_percent",
    "solar_irradiance_wm2",
    "hour",
    "day_of_week",
    "day_name",
    "month",
    "is_weekend",
    "is_working_hours",
}

MEASURE_COLUMNS = [
    "consumption_kwh",
    "consumption_euros",
    "temperature_celsius",
    "humidity_percent",
    "solar_irradiance_wm2",
]

SOURCE_NAME = "historical_csv"


def compute_sha256(path: Path) -> str:
    """Calcule l'empreinte SHA-256 du fichier source."""
    sha256 = hashlib.sha256()

    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            sha256.update(block)

    return sha256.hexdigest()


def load_metadata(path: Path) -> dict[str, Any]:
    """Charge les métadonnées fournies avec le dataset."""
    with path.open("r", encoding="utf-8") as source:
        return json.load(source)


def classify_quality(
    row: dict[str, Any],
) -> tuple[str, list[str]]:
    """
    Déduit une qualité technique à partir des champs manquants.

    Les valeurs NULL sont conservées. On ne cherche pas ici à
    déterminer la cause physique exacte de leur absence.
    """
    missing = [
        column
        for column in MEASURE_COLUMNS
        if pd.isna(row.get(column))
    ]

    if not missing:
        quality = "good"
    elif len(missing) == len(MEASURE_COLUMNS):
        quality = "critical"
    elif "consumption_kwh" in missing:
        quality = "degraded"
    else:
        quality = "partial"

    reasons = [
        f"missing:{column}"
        for column in missing
    ]

    return quality, reasons


def validate_source(
    frame: pd.DataFrame,
    metadata: dict[str, Any],
) -> None:
    """Valide le dataset avant tout chargement en base."""
    missing_columns = REQUIRED_COLUMNS.difference(
        frame.columns
    )

    if missing_columns:
        raise ValueError(
            "Colonnes obligatoires absentes : "
            f"{sorted(missing_columns)}"
        )

    expected_records = int(metadata["total_records"])

    if len(frame) != expected_records:
        raise ValueError(
            "Nombre de lignes inattendu : "
            f"{len(frame)} au lieu de "
            f"{expected_records}"
        )

    expected_sites = set(metadata["sites"].keys())
    actual_sites = set(frame["site_id"].unique())

    if actual_sites != expected_sites:
        raise ValueError(
            "Sites incohérents. "
            f"Attendus={sorted(expected_sites)}, "
            f"trouvés={sorted(actual_sites)}"
        )

    duplicated = frame.duplicated(
        subset=["site_id", "timestamp"]
    ).sum()

    if duplicated:
        raise ValueError(
            f"{duplicated} doublons "
            "(site_id, timestamp) détectés"
        )

    static_variants = (
        frame.groupby("site_id")[
            ["site_type", "site_name"]
        ]
        .nunique()
    )

    if (static_variants > 1).any().any():
        raise ValueError(
            "Un site possède plusieurs valeurs "
            "de site_type ou site_name."
        )

    # Vérifie également que tous les timestamps
    # peuvent être interprétés correctement.
    pd.to_datetime(
        frame["timestamp"],
        errors="raise",
    )


def normalize_timestamps(
    frame: pd.DataFrame,
    source_timezone: str,
) -> pd.DataFrame:
    """
    Normalise les timestamps et leur associe une timezone.

    Les timestamps originaux sont conservés dans une colonne
    temporaire afin de pouvoir les stocker dans raw_data.
    """
    normalized = frame.copy()

    normalized["_source_timestamp"] = (
        normalized["timestamp"]
    )

    timestamps = pd.to_datetime(
        normalized["timestamp"],
        errors="raise",
    )

    if timestamps.dt.tz is None:
        timestamps = timestamps.dt.tz_localize(
            source_timezone
        )
    else:
        timestamps = timestamps.dt.tz_convert(
            source_timezone
        )

    normalized["timestamp"] = timestamps

    return normalized


def to_json_value(value: Any) -> Any:
    """
    Convertit une valeur Pandas/Numpy en valeur
    compatible JSON.
    """
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if hasattr(value, "item"):
        return value.item()

    return value


async def ensure_dataset(
    connection: AsyncConnection,
    metadata: dict[str, Any],
    sha256: str,
    source_timezone: str,
    storage_uri: str,
) -> int:
    """
    Crée l'entrée dataset si elle n'existe pas.

    Le SHA-256 permet de reconnaître un fichier déjà importé
    et participe à l'idempotence et à la traçabilité.
    """
    result = await connection.execute(
        text(
            """
            SELECT dataset_id
            FROM dataset
            WHERE archive_sha256 = :sha256
            LIMIT 1
            """
        ),
        {
            "sha256": sha256,
        },
    )

    existing = result.scalar_one_or_none()

    if existing is not None:
        return int(existing)

    metadata_summary = {
        "generator_version": metadata.get(
            "generator_version"
        ),
        "total_sites": metadata.get(
            "total_sites"
        ),
        "total_records": metadata.get(
            "total_records"
        ),
        "date_range": metadata.get(
            "date_range"
        ),
        "frequency": metadata.get(
            "frequency"
        ),
        "null_injection_enabled": metadata.get(
            "null_injection_enabled"
        ),
        "null_strategies": metadata.get(
            "null_strategies"
        ),
        "importer": "historical_import_v1",
    }

    result = await connection.execute(
        text(
            """
            INSERT INTO dataset (
                dataset_name,
                archive_sha256,
                storage_uri,
                source_timezone,
                "metadata"
            )
            VALUES (
                :dataset_name,
                :archive_sha256,
                :storage_uri,
                :source_timezone,
                CAST(:metadata AS jsonb)
            )
            RETURNING dataset_id
            """
        ),
        {
            "dataset_name": (
                "EnerVision historical dataset "
                "2023-2024"
            ),
            "archive_sha256": sha256,
            "storage_uri": storage_uri,
            "source_timezone": source_timezone,
            "metadata": json.dumps(
                metadata_summary,
                ensure_ascii=False,
            ),
        },
    )

    return int(result.scalar_one())


async def upsert_sites(
    connection: AsyncConnection,
    frame: pd.DataFrame,
) -> None:
    """Insère ou met à jour les sites du dataset."""
    sites = (
        frame[
            [
                "site_id",
                "site_type",
                "site_name",
            ]
        ]
        .drop_duplicates(
            subset=["site_id"]
        )
        .to_dict(
            orient="records"
        )
    )

    await connection.execute(
        text(
            """
            INSERT INTO site (
                site_id,
                site_type,
                site_name
            )
            VALUES (
                :site_id,
                :site_type,
                :site_name
            )
            ON CONFLICT (site_id)
            DO UPDATE SET
                site_type = EXCLUDED.site_type,
                site_name = EXCLUDED.site_name
            """
        ),
        sites,
    )


def build_reading_batch(
    chunk: pd.DataFrame,
    dataset_id: int,
) -> list[dict[str, Any]]:
    """
    Transforme un chunk Pandas en lignes prêtes
    à être chargées dans la table reading.
    """
    rows: list[dict[str, Any]] = []

    for record in chunk.to_dict(
        orient="records"
    ):
        quality, reasons = classify_quality(
            record
        )

        raw_data = {
            column: to_json_value(value)
            for column, value in record.items()
            if column != "_source_timestamp"
        }

        # Dans raw_data, on conserve le timestamp
        # exactement tel qu'il était dans le CSV.
        raw_data["timestamp"] = to_json_value(
            record["_source_timestamp"]
        )

        rows.append(
            {
                "site_id": record["site_id"],
                "timestamp": record["timestamp"],
                "source": SOURCE_NAME,
                "dataset_id": dataset_id,

                # Non fourni par le dataset historique.
                "consumption_kw": None,

                "consumption_kwh": to_json_value(
                    record["consumption_kwh"]
                ),
                "consumption_euros": to_json_value(
                    record["consumption_euros"]
                ),

                # Non fournis par le CSV historique.
                "voltage_v": None,
                "current_a": None,
                "power_factor": None,

                "temperature_celsius": (
                    to_json_value(
                        record[
                            "temperature_celsius"
                        ]
                    )
                ),
                "humidity_percent": (
                    to_json_value(
                        record[
                            "humidity_percent"
                        ]
                    )
                ),
                "solar_irradiance_wm2": (
                    to_json_value(
                        record[
                            "solar_irradiance_wm2"
                        ]
                    )
                ),

                "is_working_hours": bool(
                    record[
                        "is_working_hours"
                    ]
                ),

                "data_quality": quality,
                "null_reasons": reasons,

                # Aucune imputation pendant
                # l'ingestion RAW.
                "imputed_values": json.dumps(
                    {}
                ),
                "imputation_method": None,

                # Conservation de la donnée source
                # pour la traçabilité.
                "raw_data": json.dumps(
                    raw_data,
                    ensure_ascii=False,
                ),
            }
        )

    return rows


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


async def import_historical(
    csv_path: Path,
    metadata_path: Path,
    source_timezone: str,
    batch_size: int,
    dry_run: bool,
    storage_uri: str,
) -> None:
    """
    Exécute le pipeline ETL historique EnerVision.

    Étapes :
    1. Extract
    2. Validate
    3. Transform
    4. Load
    """
    metadata = load_metadata(
        metadata_path
    )

    frame = pd.read_csv(
        csv_path
    )

    validate_source(
        frame,
        metadata,
    )

    print(
        f"Lignes             : {len(frame)}"
    )
    print(
        "Sites              : "
        f"{frame['site_id'].nunique()}"
    )
    print(
        "Période            : "
        f"{frame['timestamp'].min()} -> "
        f"{frame['timestamp'].max()}"
    )
    print(
        "Doublons           : "
        f"{frame.duplicated(['site_id', 'timestamp']).sum()}"
    )

    print("\nValeurs NULL :")
    print(
        frame[
            MEASURE_COLUMNS
        ].isna().sum()
    )

    sha256 = compute_sha256(
        csv_path
    )

    print(
        f"\nSHA-256            : {sha256}"
    )

    if dry_run:
        print(
            "\nDry-run terminé : "
            "aucune donnée écrite."
        )
        return

    normalized = normalize_timestamps(
        frame,
        source_timezone,
    )

    settings = get_settings()

    engine = create_async_engine(
        str(settings.database_url),
        pool_pre_ping=True,
    )

    try:
        async with engine.begin() as connection:
            dataset_id = await ensure_dataset(
                connection=connection,
                metadata=metadata,
                sha256=sha256,
                source_timezone=source_timezone,
                storage_uri=storage_uri,
            )

            await upsert_sites(
                connection,
                normalized,
            )

            result = await connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM reading
                    WHERE dataset_id = :dataset_id
                      AND source = :source
                    """
                ),
                {
                    "dataset_id": dataset_id,
                    "source": SOURCE_NAME,
                },
            )

            before = int(
                result.scalar_one()
            )

            for start in range(
                0,
                len(normalized),
                batch_size,
            ):
                chunk = normalized.iloc[
                    start : start + batch_size
                ]

                rows = build_reading_batch(
                    chunk,
                    dataset_id,
                )

                await connection.execute(
                    READING_INSERT,
                    rows,
                )

                loaded = min(
                    start + batch_size,
                    len(normalized),
                )

                print(
                    "Chargement : "
                    f"{loaded}/"
                    f"{len(normalized)}"
                )

            result = await connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM reading
                    WHERE dataset_id = :dataset_id
                      AND source = :source
                    """
                ),
                {
                    "dataset_id": dataset_id,
                    "source": SOURCE_NAME,
                },
            )

            after = int(
                result.scalar_one()
            )

            print(
                "\nImport terminé."
            )
            print(
                "dataset_id         : "
                f"{dataset_id}"
            )
            print(
                "lectures avant     : "
                f"{before}"
            )
            print(
                "lectures après     : "
                f"{after}"
            )
            print(
                "nouvelles lectures : "
                f"{after - before}"
            )

    finally:
        await engine.dispose()


def parse_args() -> argparse.Namespace:
    """Définit les arguments CLI de l'import."""
    parser = argparse.ArgumentParser(
        description=(
            "Import historique EnerVision"
        )
    )

    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help="Chemin vers le CSV historique.",
    )

    parser.add_argument(
        "--metadata",
        type=Path,
        required=True,
        help=(
            "Chemin vers le fichier "
            "dataset_metadata.json."
        ),
    )

    parser.add_argument(
        "--source-timezone",
        default="UTC",
        help=(
            "Timezone associée aux timestamps "
            "du dataset. Défaut : UTC."
        ),
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help=(
            "Nombre de lignes insérées "
            "par batch. Défaut : 1000."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Valide les données sans "
            "écrire en base."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """Point d'entrée CLI du pipeline."""
    args = parse_args()

    if args.batch_size <= 0:
        raise ValueError(
            "--batch-size doit être "
            "strictement supérieur à 0."
        )

    # resolve() est volontairement exécuté ici,
    # dans la partie synchrone du programme.
    # Cela évite une opération filesystem bloquante
    # à l'intérieur d'une fonction async.
    storage_uri = (
        args.csv.resolve().as_uri()
    )

    asyncio.run(
        import_historical(
            csv_path=args.csv,
            metadata_path=args.metadata,
            source_timezone=(
                args.source_timezone
            ),
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            storage_uri=storage_uri,
        )
    )


if __name__ == "__main__":
    main()
