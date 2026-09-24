import base64
import io
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import boto3
import pandas as pd
import pytest
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from botocore.stub import Stubber
from pydantic import SecretStr
from tests.factories import make_settings

import app.etl.reading_retention as reading_retention
from app.core.config import Settings
from app.etl.reading_retention import (
    CHUNK_ROWS,
    DROP_CHUNK,
    ELIGIBLE_CHUNKS,
    ArchiveStore,
    Chunk,
    Rapport,
    archive_reading_chunks,
    build_archive_store,
    build_parser,
    decode_sse_key,
    drop_chunk,
    eligible_chunks,
    object_key,
    read_chunk_rows,
    serialize_csv_gzip,
    sha256_of,
)

CLE_SSE = b"0123456789abcdef0123456789abcdef"
CLE_SSE_BASE64 = base64.b64encode(CLE_SSE).decode("ascii")

CHUNK = Chunk(
    schema="_timescaledb_internal",
    name="_hyper_1_7_chunk",
    range_start=datetime(2023, 1, 5, tzinfo=UTC),
    range_end=datetime(2023, 1, 12, tzinfo=UTC),
)
CLE_ATTENDUE = "reading/2023/reading_20230105T000000Z_20230112T000000Z.csv.gz"


def make_row(**overrides: Any) -> dict[str, Any]:
    ligne: dict[str, Any] = {
        "reading_id": 1,
        "site_id": "SITE001",
        "timestamp": datetime(2023, 1, 5, 12, tzinfo=UTC),
        "source": "csv",
        "dataset_id": 1,
        "consumption_kw": Decimal("87.34"),
        "data_quality": "good",
        "null_reasons": ["sensor_offline"],
        "imputed_values": None,
        "raw_data": {"b": 1, "a": "é"},
    }
    return {**ligne, **overrides}


def settings_s3(**overrides: Any) -> Settings:
    reglages: dict[str, Any] = {
        "_env_file": None,
        "secret_key": SecretStr("secret-de-test-assez-long-pour-le-validateur"),
        "database_url": "postgresql+asyncpg://retention:test@localhost:5432/enervision",
        "s3_endpoint_url": "http://garage:3900",
        "s3_access_key": "GK0123456789",
        "s3_secret_key": SecretStr("un-secret-garage"),
        "s3_bucket": "enervision-archives",
        "s3_sse_key": SecretStr(CLE_SSE_BASE64),
    }
    return Settings(**{**reglages, **overrides})


def s3_client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url="http://garage:3900",
        aws_access_key_id="GK0123456789",
        aws_secret_access_key="un-secret-garage",
        region_name="garage",
    )


def streaming(data: bytes) -> StreamingBody:
    return StreamingBody(io.BytesIO(data), len(data))


def test_settings_treat_empty_s3_values_as_absent() -> None:
    settings = make_settings(
        s3_endpoint_url="", s3_access_key="", s3_secret_key="", s3_bucket="", s3_sse_key=""
    )

    assert settings.s3_endpoint_url is None
    assert settings.s3_access_key is None
    assert settings.s3_secret_key is None
    assert settings.s3_bucket is None
    assert settings.s3_sse_key is None
    assert settings.reading_retention_days == 1095


def test_object_key_places_the_chunk_under_the_year_of_its_start() -> None:
    assert object_key(CHUNK) == CLE_ATTENDUE


def test_object_key_expresses_the_bounds_in_utc() -> None:
    paris = timezone(timedelta(hours=1))
    chunk = Chunk(
        schema=CHUNK.schema,
        name=CHUNK.name,
        range_start=datetime(2023, 1, 5, 1, tzinfo=paris),
        range_end=datetime(2023, 1, 12, 1, tzinfo=paris),
    )

    assert object_key(chunk) == CLE_ATTENDUE


def test_serialize_csv_gzip_is_read_back_by_pandas() -> None:
    archive = serialize_csv_gzip([make_row(), make_row(reading_id=2, null_reasons=[])])

    relu = pd.read_csv(io.BytesIO(archive), compression="gzip")

    assert list(relu.columns) == list(make_row())
    assert relu["reading_id"].tolist() == [1, 2]
    assert relu["site_id"].tolist() == ["SITE001", "SITE001"]


def test_serialize_csv_gzip_writes_jsonb_and_arrays_as_sorted_json() -> None:
    archive = serialize_csv_gzip([make_row()])

    relu = pd.read_csv(io.BytesIO(archive), compression="gzip")

    assert relu.loc[0, "raw_data"] == '{"a": "é", "b": 1}'
    assert relu.loc[0, "null_reasons"] == '["sensor_offline"]'


def test_serialize_csv_gzip_is_byte_for_byte_reproducible() -> None:
    lignes = [make_row(), make_row(reading_id=2)]

    assert serialize_csv_gzip(lignes) == serialize_csv_gzip(lignes)


def test_serialize_csv_gzip_refuses_an_empty_export() -> None:
    with pytest.raises(ValueError, match="Aucune ligne"):
        serialize_csv_gzip([])


def test_sha256_of_hashes_the_bytes() -> None:
    assert sha256_of(b"hello").startswith("2cf24dba")


def test_store_put_sends_the_sse_c_headers_when_a_key_is_set() -> None:
    client = s3_client()
    store = ArchiveStore(client, bucket="enervision-archives", sse_key=CLE_SSE)

    with Stubber(client) as stub:
        stub.add_response(
            "put_object",
            {},
            expected_params={
                "Bucket": "enervision-archives",
                "Key": CLE_ATTENDUE,
                "Body": b"corps",
                "ContentType": "text/csv",
                "ContentEncoding": "gzip",
                "Metadata": {"sha256": "abc"},
                "SSECustomerAlgorithm": "AES256",
                "SSECustomerKey": CLE_SSE,
            },
        )
        store.put(CLE_ATTENDUE, b"corps", {"sha256": "abc"})
        stub.assert_no_pending_responses()


def test_store_put_omits_the_sse_c_headers_without_a_key() -> None:
    client = s3_client()
    store = ArchiveStore(client, bucket="enervision-archives", sse_key=None)

    with Stubber(client) as stub:
        stub.add_response(
            "put_object",
            {},
            expected_params={
                "Bucket": "enervision-archives",
                "Key": CLE_ATTENDUE,
                "Body": b"corps",
                "ContentType": "text/csv",
                "ContentEncoding": "gzip",
                "Metadata": {},
            },
        )
        store.put(CLE_ATTENDUE, b"corps", {})
        stub.assert_no_pending_responses()


def test_store_fetch_sha256_hashes_the_object_read_with_the_key() -> None:
    client = s3_client()
    store = ArchiveStore(client, bucket="enervision-archives", sse_key=CLE_SSE)

    with Stubber(client) as stub:
        stub.add_response(
            "get_object",
            {"Body": streaming(b"hello")},
            expected_params={
                "Bucket": "enervision-archives",
                "Key": CLE_ATTENDUE,
                "SSECustomerAlgorithm": "AES256",
                "SSECustomerKey": CLE_SSE,
            },
        )

        assert store.fetch_sha256(CLE_ATTENDUE) == sha256_of(b"hello")


@pytest.mark.parametrize(
    ("code", "statut"),
    [("NoSuchKey", 404), ("NotFound", 404), ("NoSuchKey", 400)],
    ids=["no_such_key", "404_sans_code_connu", "no_such_key_sans_404"],
)
def test_store_fetch_sha256_returns_none_for_a_missing_object(code: str, statut: int) -> None:
    client = s3_client()
    store = ArchiveStore(client, bucket="enervision-archives", sse_key=None)

    with Stubber(client) as stub:
        stub.add_client_error("get_object", service_error_code=code, http_status_code=statut)

        assert store.fetch_sha256(CLE_ATTENDUE) is None


def test_store_fetch_sha256_raises_any_other_error() -> None:
    client = s3_client()
    store = ArchiveStore(client, bucket="enervision-archives", sse_key=None)

    with Stubber(client) as stub:
        stub.add_client_error("get_object", service_error_code="AccessDenied", http_status_code=403)

        with pytest.raises(ClientError):
            store.fetch_sha256(CLE_ATTENDUE)


def test_decode_sse_key_returns_none_without_a_key() -> None:
    assert decode_sse_key(None) is None


def test_decode_sse_key_decodes_the_base64_key() -> None:
    assert decode_sse_key(SecretStr(CLE_SSE_BASE64)) == CLE_SSE


def test_decode_sse_key_refuses_a_key_of_the_wrong_length() -> None:
    courte = base64.b64encode(b"trop-courte").decode("ascii")

    with pytest.raises(ValueError, match="exactement 32 octets"):
        decode_sse_key(SecretStr(courte))


@pytest.mark.parametrize(
    "manquant",
    ["s3_endpoint_url", "s3_access_key", "s3_secret_key", "s3_bucket"],
)
def test_build_archive_store_refuses_a_missing_setting(manquant: str) -> None:
    with pytest.raises(ValueError, match="APP_S3_ENDPOINT_URL"):
        build_archive_store(settings_s3(**{manquant: None}))


def test_build_archive_store_refuses_a_sse_key_of_the_wrong_length() -> None:
    courte = base64.b64encode(b"trop-courte").decode("ascii")

    with pytest.raises(ValueError, match="exactement 32 octets"):
        build_archive_store(settings_s3(s3_sse_key=SecretStr(courte)))


def test_build_archive_store_configures_the_client_from_the_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recu: dict[str, Any] = {}

    def faux_client(service: str, **kwargs: Any) -> MagicMock:
        recu["service"] = service
        recu.update(kwargs)
        return MagicMock()

    monkeypatch.setattr(reading_retention.boto3, "client", faux_client)

    build_archive_store(settings_s3())

    assert recu == {
        "service": "s3",
        "endpoint_url": "http://garage:3900",
        "aws_access_key_id": "GK0123456789",
        "aws_secret_access_key": "un-secret-garage",
        "region_name": "garage",
    }


def test_build_archive_store_uses_the_bucket_and_the_decoded_key() -> None:
    store = build_archive_store(settings_s3())

    with Stubber(store._client) as stub:
        stub.add_response(
            "get_object",
            {"Body": streaming(b"hello")},
            expected_params={
                "Bucket": "enervision-archives",
                "Key": CLE_ATTENDUE,
                "SSECustomerAlgorithm": "AES256",
                "SSECustomerKey": CLE_SSE,
            },
        )

        assert store.fetch_sha256(CLE_ATTENDUE) == sha256_of(b"hello")


def test_build_archive_store_accepts_an_absent_sse_key() -> None:
    store = build_archive_store(settings_s3(s3_sse_key=None))

    with Stubber(store._client) as stub:
        stub.add_response(
            "get_object",
            {"Body": streaming(b"hello")},
            expected_params={"Bucket": "enervision-archives", "Key": CLE_ATTENDUE},
        )

        assert store.fetch_sha256(CLE_ATTENDUE) == sha256_of(b"hello")


class FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def mappings(self) -> FakeResult:
        return self

    def scalars(self) -> FakeResult:
        return self

    def all(self) -> list[Any]:
        return self._rows


def chunk_mapping(chunk: Chunk) -> dict[str, Any]:
    return {
        "chunk_schema": chunk.schema,
        "chunk_name": chunk.name,
        "range_start": chunk.range_start,
        "range_end": chunk.range_end,
    }


async def test_eligible_chunks_queries_the_timescaledb_catalog() -> None:
    conn = AsyncMock()
    conn.execute.return_value = FakeResult([chunk_mapping(CHUNK)])
    borne = datetime(2023, 10, 1, tzinfo=UTC)

    chunks = await eligible_chunks(conn, borne)

    assert chunks == [CHUNK]
    statement, params = conn.execute.await_args.args
    assert statement is ELIGIBLE_CHUNKS
    assert params == {"older_than": borne}


async def test_read_chunk_rows_reads_through_the_hypertable_within_the_chunk_bounds() -> None:
    conn = AsyncMock()
    conn.execute.return_value = FakeResult([make_row(), make_row(reading_id=2)])

    lignes = await read_chunk_rows(conn, CHUNK)

    assert lignes == [make_row(), make_row(reading_id=2)]
    statement, params = conn.execute.await_args.args
    assert statement is CHUNK_ROWS
    assert params == {"start": CHUNK.range_start, "end": CHUNK.range_end}


async def test_drop_chunk_targets_the_chunk_by_its_own_bounds() -> None:
    conn = AsyncMock()
    conn.execute.return_value = FakeResult([CHUNK.qualified_name])

    await drop_chunk(conn, CHUNK)

    statement, params = conn.execute.await_args.args
    assert statement is DROP_CHUNK
    assert params == {"start": CHUNK.range_start, "end": CHUNK.range_end}


@pytest.mark.parametrize(
    "rendu",
    [[], ["_timescaledb_internal._hyper_1_7_chunk", "_timescaledb_internal._hyper_1_8_chunk"]],
    ids=["aucun_chunk", "deux_chunks"],
)
async def test_drop_chunk_raises_unless_exactly_the_chunk_was_dropped(rendu: list[str]) -> None:
    conn = AsyncMock()
    conn.execute.return_value = FakeResult(rendu)

    with pytest.raises(RuntimeError, match=r"exactement _timescaledb_internal\._hyper_1_7_chunk"):
        await drop_chunk(conn, CHUNK)


class FakeConn:
    def __init__(self, journal: list[str], chunks: list[Chunk], rows: list[dict[str, Any]]) -> None:
        self._journal = journal
        self._chunks = chunks
        self._rows = rows

    async def execute(self, statement: Any, params: dict[str, Any]) -> FakeResult:
        if statement is ELIGIBLE_CHUNKS:
            self._journal.append("lister")
            return FakeResult([chunk_mapping(chunk) for chunk in self._chunks])
        if statement is CHUNK_ROWS:
            self._journal.append("lire")
            return FakeResult(self._rows)
        self._journal.append("drop")
        chunk = next(c for c in self._chunks if c.range_start == params["start"])
        return FakeResult([chunk.qualified_name])


class FakeEngine:
    def __init__(self, conn: FakeConn, journal: list[str]) -> None:
        self._conn = conn
        self._journal = journal

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[FakeConn]:
        self._journal.append("connect")
        yield self._conn

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[FakeConn]:
        self._journal.append("begin")
        yield self._conn

    async def dispose(self) -> None:
        self._journal.append("dispose")


class FakeStore(ArchiveStore):
    def __init__(self, journal: list[str], *, corrompt: bool = False) -> None:
        super().__init__(MagicMock(), bucket="enervision-archives", sse_key=None)
        self._journal = journal
        self._corrompt = corrompt
        self.objets: dict[str, str] = {}
        self.metadata: dict[str, dict[str, str]] = {}

    def put(self, key: str, body: bytes, metadata: dict[str, str]) -> None:
        self._journal.append("put")
        self.objets[key] = "sha-corrompu" if self._corrompt else sha256_of(body)
        self.metadata[key] = metadata

    def fetch_sha256(self, key: str) -> str | None:
        self._journal.append("relire")
        return self.objets.get(key)


def make_archive(
    chunks: list[Chunk] | None = None,
    rows: list[dict[str, Any]] | None = None,
    *,
    corrompt: bool = False,
) -> tuple[FakeEngine, FakeStore, list[str]]:
    journal: list[str] = []
    lignes = [make_row(), make_row(reading_id=2)] if rows is None else rows
    eligibles = [CHUNK] if chunks is None else chunks
    engine = FakeEngine(FakeConn(journal, eligibles, lignes), journal)
    return engine, FakeStore(journal, corrompt=corrompt), journal


async def test_archive_reading_chunks_reads_exports_verifies_then_drops(
    capsys: pytest.CaptureFixture[str],
) -> None:
    engine, store, journal = make_archive()
    borne = datetime(2023, 10, 1, tzinfo=UTC)

    rapport = await archive_reading_chunks(engine, store, older_than=borne, dry_run=False)

    assert journal == [
        "connect",
        "lister",
        "connect",
        "lire",
        "relire",
        "put",
        "relire",
        "begin",
        "drop",
    ]
    assert rapport == Rapport(chunks_vus=1, exportes=1, deja_presents=0, supprimes=1, lignes=2)
    assert store.objets[CLE_ATTENDUE] == sha256_of(
        serialize_csv_gzip([make_row(), make_row(reading_id=2)])
    )
    assert store.metadata[CLE_ATTENDUE] == {"sha256": store.objets[CLE_ATTENDUE], "rows": "2"}

    sortie = capsys.readouterr().out
    assert f"{CLE_ATTENDUE} : 2 ligne(s)" in sortie
    assert "exportés et relus" in sortie
    assert f"chunk {CHUNK.qualified_name} supprimé" in sortie
    assert "Archivage terminé." in sortie


async def test_archive_reading_chunks_skips_the_upload_when_the_object_already_matches() -> None:
    engine, store, journal = make_archive()
    store.objets[CLE_ATTENDUE] = sha256_of(serialize_csv_gzip([make_row(), make_row(reading_id=2)]))

    rapport = await archive_reading_chunks(
        engine, store, older_than=datetime(2023, 10, 1, tzinfo=UTC), dry_run=False
    )

    assert "put" not in journal
    assert journal[-2:] == ["begin", "drop"]
    assert rapport == Rapport(chunks_vus=1, exportes=0, deja_presents=1, supprimes=1, lignes=2)


async def test_archive_reading_chunks_re_uploads_when_the_stored_object_differs() -> None:
    engine, store, journal = make_archive()
    store.objets[CLE_ATTENDUE] = "un-autre-sha"

    rapport = await archive_reading_chunks(
        engine, store, older_than=datetime(2023, 10, 1, tzinfo=UTC), dry_run=False
    )

    assert journal.count("put") == 1
    assert rapport.exportes == 1
    assert rapport.deja_presents == 0


async def test_archive_reading_chunks_in_dry_run_neither_writes_nor_drops(
    capsys: pytest.CaptureFixture[str],
) -> None:
    engine, store, journal = make_archive()

    rapport = await archive_reading_chunks(
        engine, store, older_than=datetime(2023, 10, 1, tzinfo=UTC), dry_run=True
    )

    assert "put" not in journal
    assert "begin" not in journal
    assert "drop" not in journal
    assert rapport == Rapport(chunks_vus=1, exportes=0, deja_presents=0, supprimes=0, lignes=2)

    sortie = capsys.readouterr().out
    assert "octets à exporter, suppression simulée." in sortie
    assert "Dry-run terminé : rien n'a été écrit ni supprimé." in sortie


async def test_archive_reading_chunks_keeps_the_chunk_when_the_read_back_differs() -> None:
    engine, store, journal = make_archive(corrompt=True)

    with pytest.raises(RuntimeError, match="sha256 sha-corrompu au lieu de"):
        await archive_reading_chunks(
            engine, store, older_than=datetime(2023, 10, 1, tzinfo=UTC), dry_run=False
        )

    assert "put" in journal
    assert "drop" not in journal


async def test_archive_reading_chunks_drops_an_empty_chunk_without_exporting(
    capsys: pytest.CaptureFixture[str],
) -> None:
    engine, store, journal = make_archive(rows=[])

    rapport = await archive_reading_chunks(
        engine, store, older_than=datetime(2023, 10, 1, tzinfo=UTC), dry_run=False
    )

    assert "put" not in journal
    assert "relire" not in journal
    assert journal[-2:] == ["begin", "drop"]
    assert rapport == Rapport(chunks_vus=1, exportes=0, deja_presents=0, supprimes=1, lignes=0)
    assert "vide, rien à exporter" in capsys.readouterr().out


async def test_archive_reading_chunks_handles_each_chunk_in_turn() -> None:
    suivant = Chunk(
        schema=CHUNK.schema,
        name="_hyper_1_8_chunk",
        range_start=CHUNK.range_end,
        range_end=CHUNK.range_end + timedelta(days=7),
    )
    engine, store, journal = make_archive(chunks=[CHUNK, suivant])

    rapport = await archive_reading_chunks(
        engine, store, older_than=datetime(2023, 10, 1, tzinfo=UTC), dry_run=False
    )

    assert rapport == Rapport(chunks_vus=2, exportes=2, deja_presents=0, supprimes=2, lignes=4)
    assert set(store.objets) == {CLE_ATTENDUE, object_key(suivant)}
    assert journal.count("drop") == 2


async def test_archive_reading_chunks_reports_nothing_to_do_without_eligible_chunks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    engine, store, journal = make_archive(chunks=[])

    rapport = await archive_reading_chunks(
        engine, store, older_than=datetime(2023, 10, 1, tzinfo=UTC), dry_run=False
    )

    assert rapport == Rapport()
    assert journal == ["connect", "lister"]
    assert "0 chunk(s) de reading" in capsys.readouterr().out


def test_build_parser_defaults_to_the_settings_and_a_real_run() -> None:
    arguments = build_parser().parse_args([])

    assert arguments.older_than_days is None
    assert arguments.dry_run is False


def test_build_parser_reads_the_bound_and_the_dry_run() -> None:
    arguments = build_parser().parse_args(["--older-than-days", "400", "--dry-run"])

    assert arguments.older_than_days == 400
    assert arguments.dry_run is True


def test_build_parser_refuses_a_non_integer_bound() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--older-than-days", "un-an"])


def test_build_parser_answers_help_without_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)

    with pytest.raises(SystemExit) as sortie:
        build_parser().parse_args(["--help"])

    assert sortie.value.code == 0


@pytest.fixture
def main_branche(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    capture: dict[str, Any] = {}
    journal: list[str] = []
    engine = FakeEngine(FakeConn(journal, [], []), journal)
    store = FakeStore(journal)

    async def faux_archive(
        engine_recu: Any, store_recu: Any, *, older_than: datetime, dry_run: bool
    ) -> Rapport:
        capture.update(engine=engine_recu, store=store_recu, older_than=older_than, dry_run=dry_run)
        return Rapport()

    def faux_engine(url: str, **kwargs: Any) -> FakeEngine:
        capture["url"] = url
        capture["engine_kwargs"] = kwargs
        return engine

    monkeypatch.setattr(reading_retention, "get_settings", settings_s3)
    monkeypatch.setattr(reading_retention, "build_archive_store", lambda settings: store)
    monkeypatch.setattr(reading_retention, "create_async_engine", faux_engine)
    monkeypatch.setattr(reading_retention, "archive_reading_chunks", faux_archive)
    capture["journal"] = journal
    capture["store_attendu"] = store
    capture["engine_attendu"] = engine
    return capture


def test_main_uses_the_retention_setting_by_default(main_branche: dict[str, Any]) -> None:
    avant = datetime.now(UTC)

    reading_retention.main([])

    attendu = avant - timedelta(days=1095)
    assert timedelta(0) <= main_branche["older_than"] - attendu < timedelta(seconds=5)
    assert main_branche["dry_run"] is False
    assert main_branche["store"] is main_branche["store_attendu"]
    assert main_branche["engine"] is main_branche["engine_attendu"]
    assert main_branche["url"] == "postgresql+asyncpg://retention:test@localhost:5432/enervision"
    assert main_branche["engine_kwargs"] == {"pool_pre_ping": True}
    assert main_branche["journal"] == ["dispose"]


def test_main_honours_an_explicit_bound_and_the_dry_run(main_branche: dict[str, Any]) -> None:
    avant = datetime.now(UTC)

    reading_retention.main(["--older-than-days", "10", "--dry-run"])

    attendu = avant - timedelta(days=10)
    assert timedelta(0) <= main_branche["older_than"] - attendu < timedelta(seconds=5)
    assert main_branche["dry_run"] is True


def test_main_fails_before_touching_the_database_without_s3_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(reading_retention, "get_settings", lambda: settings_s3(s3_bucket=None))
    monkeypatch.setattr(
        reading_retention,
        "create_async_engine",
        lambda *_, **__: pytest.fail("l'engine ne doit pas être créé"),
    )

    with pytest.raises(ValueError, match="APP_S3_BUCKET"):
        reading_retention.main([])
