# Pourquoi : la suppression n'est pas confiée à add_retention_policy, qui ignorerait l'export.
# archive_reading_chunks() exporte chaque chunk vers Garage, le relit, puis le supprime seul.
# Piège : drop_chunks pose un verrou exclusif sur reading, site et dataset jusqu'au COMMIT. La
# suppression tient donc dans une transaction dédiée et courte, séparée de la lecture du chunk.

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import anyio.to_thread
import boto3
import pandas as pd
from botocore.exceptions import ClientError
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app.core.config import Settings, get_settings

if TYPE_CHECKING:
    from types_boto3_s3.client import S3Client

SSE_KEY_LENGTH = 32
FORMAT_BORNE = "%Y%m%dT%H%M%SZ"

ELIGIBLE_CHUNKS = text(
    "SELECT chunk_schema, chunk_name, range_start, range_end "
    "FROM timescaledb_information.chunks "
    "WHERE hypertable_name = 'reading' AND range_end <= :older_than "
    "ORDER BY range_start"
)

# Lecture via l'hypertable, jamais la table interne : l'exclusion de partition vise le seul chunk.
CHUNK_ROWS = text(
    "SELECT * FROM reading WHERE timestamp >= :start AND timestamp < :end "
    "ORDER BY timestamp, reading_id"
)

# Les deux bornes sont inclusives pour drop_chunks : celles du chunk le désignent, et lui seul.
DROP_CHUNK = text(
    "SELECT drop_chunks('reading', "
    "older_than => CAST(:end AS timestamptz), newer_than => CAST(:start AS timestamptz))"
)


@dataclass(frozen=True)
class Chunk:
    schema: str
    name: str
    range_start: datetime
    range_end: datetime

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.name}"


@dataclass
class Rapport:
    chunks_vus: int = 0
    exportes: int = 0
    deja_presents: int = 0
    supprimes: int = 0
    lignes: int = 0


def object_key(chunk: Chunk) -> str:
    start = chunk.range_start.astimezone(UTC)
    end = chunk.range_end.astimezone(UTC)
    return (
        f"reading/{start.year}/reading_{start.strftime(FORMAT_BORNE)}_"
        f"{end.strftime(FORMAT_BORNE)}.csv.gz"
    )


async def eligible_chunks(conn: AsyncConnection, older_than: datetime) -> list[Chunk]:
    result = await conn.execute(ELIGIBLE_CHUNKS, {"older_than": older_than})
    return [
        Chunk(
            schema=row["chunk_schema"],
            name=row["chunk_name"],
            range_start=row["range_start"],
            range_end=row["range_end"],
        )
        for row in result.mappings().all()
    ]


async def read_chunk_rows(conn: AsyncConnection, chunk: Chunk) -> list[dict[str, Any]]:
    result = await conn.execute(CHUNK_ROWS, {"start": chunk.range_start, "end": chunk.range_end})
    return [dict(row) for row in result.mappings().all()]


def _csv_cell(value: object) -> object:
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def serialize_csv_gzip(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        raise ValueError("Aucune ligne à sérialiser : un CSV sans colonne ne se relit pas.")

    frame = pd.DataFrame([{name: _csv_cell(value) for name, value in row.items()} for row in rows])
    buffer = io.BytesIO()
    frame.to_csv(buffer, mode="wb", index=False, compression={"method": "gzip", "mtime": 0})
    return buffer.getvalue()


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_missing_object(erreur: ClientError) -> bool:
    error = erreur.response.get("Error")
    metadata = erreur.response.get("ResponseMetadata")
    code = error.get("Code") if error is not None else None
    status = metadata.get("HTTPStatusCode") if metadata is not None else None
    return code == "NoSuchKey" or status == 404


class ArchiveStore:
    def __init__(self, client: S3Client, bucket: str, sse_key: bytes | None) -> None:
        self._client = client
        self._bucket = bucket
        self._sse_key = sse_key

    # boto3 encode lui-même la clé en base64 et calcule son MD5 : la fournir brute, sans MD5.
    def _sse_headers(self) -> dict[str, Any]:
        if self._sse_key is None:
            return {}
        return {"SSECustomerAlgorithm": "AES256", "SSECustomerKey": self._sse_key}

    def put(self, key: str, body: bytes, metadata: dict[str, str]) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=body,
            ContentType="text/csv",
            ContentEncoding="gzip",
            Metadata=metadata,
            **self._sse_headers(),
        )

    def fetch_sha256(self, key: str) -> str | None:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key, **self._sse_headers())
        except ClientError as erreur:
            if _is_missing_object(erreur):
                return None
            raise
        return sha256_of(response["Body"].read())


def decode_sse_key(encoded: SecretStr | None) -> bytes | None:
    if encoded is None:
        return None

    key = base64.b64decode(encoded.get_secret_value(), validate=True)
    if len(key) != SSE_KEY_LENGTH:
        raise ValueError(
            f"APP_S3_SSE_KEY doit encoder exactement {SSE_KEY_LENGTH} octets en base64, "
            f"pas {len(key)}."
        )
    return key


def build_archive_store(settings: Settings) -> ArchiveStore:
    endpoint = settings.s3_endpoint_url
    access_key = settings.s3_access_key
    secret_key = settings.s3_secret_key
    bucket = settings.s3_bucket

    if endpoint is None or access_key is None or secret_key is None or bucket is None:
        raise ValueError(
            "L'archivage vers Garage exige APP_S3_ENDPOINT_URL, APP_S3_ACCESS_KEY, "
            "APP_S3_SECRET_KEY et APP_S3_BUCKET."
        )

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key.get_secret_value(),
        region_name=settings.s3_region,
    )
    return ArchiveStore(client, bucket=bucket, sse_key=decode_sse_key(settings.s3_sse_key))


async def drop_chunk(conn: AsyncConnection, chunk: Chunk) -> None:
    result = await conn.execute(DROP_CHUNK, {"start": chunk.range_start, "end": chunk.range_end})
    supprimes = list(result.scalars().all())

    if supprimes != [chunk.qualified_name]:
        raise RuntimeError(
            f"drop_chunks devait supprimer exactement {chunk.qualified_name}, "
            f"il a rendu {supprimes}."
        )


async def _export(
    store: ArchiveStore,
    key: str,
    rows: list[dict[str, Any]],
    *,
    dry_run: bool,
    rapport: Rapport,
) -> str:
    body = serialize_csv_gzip(rows)
    sha = sha256_of(body)

    if await anyio.to_thread.run_sync(store.fetch_sha256, key) == sha:
        rapport.deja_presents += 1
        return f"{len(body)} octets déjà présents"

    if dry_run:
        return f"{len(body)} octets à exporter"

    metadata = {"sha256": sha, "rows": str(len(rows))}
    await anyio.to_thread.run_sync(store.put, key, body, metadata)
    relu = await anyio.to_thread.run_sync(store.fetch_sha256, key)

    if relu != sha:
        raise RuntimeError(
            f"Relecture de {key} : sha256 {relu} au lieu de {sha}, le chunk est conservé."
        )

    rapport.exportes += 1
    return f"{len(body)} octets exportés et relus"


async def _archive_chunk(
    engine: AsyncEngine,
    store: ArchiveStore,
    chunk: Chunk,
    *,
    dry_run: bool,
    rapport: Rapport,
) -> None:
    async with engine.connect() as conn:
        rows = await read_chunk_rows(conn, chunk)

    key = object_key(chunk)
    rapport.lignes += len(rows)

    if rows:
        action = await _export(store, key, rows, dry_run=dry_run, rapport=rapport)
    else:
        action = "vide, rien à exporter"

    if dry_run:
        print(f"{key} : {len(rows)} ligne(s), {action}, suppression simulée.")
        return

    async with engine.begin() as conn:
        await drop_chunk(conn, chunk)

    rapport.supprimes += 1
    print(f"{key} : {len(rows)} ligne(s), {action}, chunk {chunk.qualified_name} supprimé.")


async def archive_reading_chunks(
    engine: AsyncEngine,
    store: ArchiveStore,
    *,
    older_than: datetime,
    dry_run: bool,
) -> Rapport:
    rapport = Rapport()

    async with engine.connect() as conn:
        chunks = await eligible_chunks(conn, older_than)

    rapport.chunks_vus = len(chunks)
    print(
        f"{len(chunks)} chunk(s) de reading entièrement antérieur(s) au {older_than.isoformat()}."
    )

    for chunk in chunks:
        await _archive_chunk(engine, store, chunk, dry_run=dry_run, rapport=rapport)

    bilan = "Dry-run terminé : rien n'a été écrit ni supprimé." if dry_run else "Archivage terminé."
    print(
        f"{bilan} Chunks vus : {rapport.chunks_vus}, exportés : {rapport.exportes}, "
        f"déjà présents : {rapport.deja_presents}, supprimés : {rapport.supprimes}, "
        f"lignes : {rapport.lignes}."
    )
    return rapport


async def _run(
    settings: Settings,
    store: ArchiveStore,
    *,
    older_than: datetime,
    dry_run: bool,
) -> Rapport:
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    try:
        return await archive_reading_chunks(engine, store, older_than=older_than, dry_run=dry_run)
    finally:
        await engine.dispose()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.etl.reading_retention",
        description=(
            "Exporte vers Garage puis supprime les chunks de reading entièrement plus vieux "
            "que la borne de rétention."
        ),
    )
    parser.add_argument(
        "--older-than-days",
        type=int,
        default=None,
        help="Borne en jours, par défaut APP_READING_RETENTION_DAYS.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Liste et mesure les chunks éligibles sans rien écrire ni supprimer.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    settings = get_settings()

    jours = (
        settings.reading_retention_days if args.older_than_days is None else args.older_than_days
    )
    older_than = datetime.now(UTC) - timedelta(days=jours)
    store = build_archive_store(settings)

    asyncio.run(_run(settings, store, older_than=older_than, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
