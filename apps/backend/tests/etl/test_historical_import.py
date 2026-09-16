import hashlib
import json

import pandas as pd
import pytest

from app.etl.historical_import import (
    SOURCE_NAME,
    build_reading_batch,
    classify_quality,
    compute_sha256,
    load_metadata,
    normalize_timestamps,
    validate_source,
)


def make_metadata() -> dict:
    return {
        "total_records": 2,
        "sites": {
            "SITE001": {},
        },
    }


def make_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp": "2023-01-01 00:00:00",
                "site_id": "SITE001",
                "site_type": "office",
                "site_name": "Site 1",
                "consumption_kwh": 10.5,
                "consumption_euros": 2.5,
                "temperature_celsius": 20.0,
                "humidity_percent": 50.0,
                "solar_irradiance_wm2": 0.0,
                "hour": 0,
                "day_of_week": 6,
                "day_name": "Sunday",
                "month": 1,
                "is_weekend": True,
                "is_working_hours": False,
            },
            {
                "timestamp": "2023-01-01 01:00:00",
                "site_id": "SITE001",
                "site_type": "office",
                "site_name": "Site 1",
                "consumption_kwh": 11.0,
                "consumption_euros": 2.7,
                "temperature_celsius": 19.5,
                "humidity_percent": 52.0,
                "solar_irradiance_wm2": 0.0,
                "hour": 1,
                "day_of_week": 6,
                "day_name": "Sunday",
                "month": 1,
                "is_weekend": True,
                "is_working_hours": False,
            },
        ]
    )


def test_compute_sha256(tmp_path):
    file_path = tmp_path / "dataset.csv"
    content = b"hello-enervision"

    file_path.write_bytes(content)

    expected = hashlib.sha256(content).hexdigest()

    assert compute_sha256(file_path) == expected


def test_load_metadata(tmp_path):
    metadata_path = tmp_path / "metadata.json"

    metadata = {
        "total_records": 2,
        "sites": {
            "SITE001": {},
        },
    }

    metadata_path.write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )

    assert load_metadata(metadata_path) == metadata


def test_validate_source_accepts_valid_dataset():
    frame = make_dataframe()

    validate_source(
        frame,
        make_metadata(),
    )


def test_validate_source_rejects_missing_column():
    frame = make_dataframe().drop(
        columns=["consumption_kwh"]
    )

    with pytest.raises(
        ValueError,
        match="Colonnes obligatoires absentes",
    ):
        validate_source(
            frame,
            make_metadata(),
        )


def test_validate_source_rejects_duplicates():
    frame = make_dataframe()

    frame.loc[1, "timestamp"] = frame.loc[
        0,
        "timestamp",
    ]

    with pytest.raises(
        ValueError,
        match="doublons",
    ):
        validate_source(
            frame,
            make_metadata(),
        )


def test_validate_source_rejects_unknown_site():
    frame = make_dataframe()

    frame.loc[1, "site_id"] = "SITE999"

    with pytest.raises(
        ValueError,
        match="Sites incohérents",
    ):
        validate_source(
            frame,
            make_metadata(),
        )


def test_normalize_timestamps_adds_timezone():
    frame = make_dataframe()

    normalized = normalize_timestamps(
        frame,
        "UTC",
    )

    assert normalized["timestamp"].dt.tz is not None

    assert "_source_timestamp" in normalized.columns


def test_classify_quality_good():
    row = make_dataframe().iloc[0].to_dict()

    quality, reasons = classify_quality(row)

    assert quality == "good"
    assert reasons == []


def test_classify_quality_degraded_when_consumption_missing():
    row = make_dataframe().iloc[0].to_dict()
    row["consumption_kwh"] = None

    quality, reasons = classify_quality(row)

    assert quality == "degraded"

    assert "missing:consumption_kwh" in reasons


def test_build_reading_batch_respects_database_contract():
    frame = normalize_timestamps(
        make_dataframe(),
        "UTC",
    )

    rows = build_reading_batch(
        frame.iloc[:1],
        dataset_id=3,
    )

    assert len(rows) == 1

    row = rows[0]

    assert row["dataset_id"] == 3

    # Important :
    # contrainte ck_reading_dataset_source.
    assert row["source"] == "csv"
    assert SOURCE_NAME == "csv"

    # Important :
    # contrainte ck_reading_imputation.
    assert row["imputed_values"] is None
    assert row["imputation_method"] is None

    assert row["data_quality"] == "good"
    assert row["null_reasons"] == []


def test_build_reading_batch_keeps_missing_values():
    frame = make_dataframe()

    frame.loc[0, "temperature_celsius"] = None

    frame = normalize_timestamps(
        frame,
        "UTC",
    )

    rows = build_reading_batch(
        frame.iloc[:1],
        dataset_id=3,
    )

    row = rows[0]

    assert row["temperature_celsius"] is None

    assert (
        "missing:temperature_celsius"
        in row["null_reasons"]
    )

    # RAW ingestion : aucune imputation.
    assert row["imputed_values"] is None
    assert row["imputation_method"] is None
