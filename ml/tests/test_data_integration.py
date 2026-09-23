from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import Connection

from enervision_ml.data import (
    OUTPUT_COLUMNS,
    load_from_csv,
    load_from_database,
    load_recent_from_database,
)
from tests.conftest import ANCRAGE, insere_lecture, insere_lectures, insere_site

pytestmark = pytest.mark.integration


def test_load_from_database_returns_the_nine_contract_columns(connexion_ml: Connection) -> None:
    site_id = insere_site(connexion_ml)
    insere_lectures(connexion_ml, site_id, heures=3, fin=ANCRAGE)

    frame = load_from_database(connexion_ml)

    assert list(frame.columns) == OUTPUT_COLUMNS


def test_load_from_database_joins_the_site_attributes_to_every_reading(
    connexion_ml: Connection,
) -> None:
    site_id = insere_site(connexion_ml, site_type="factory", capacity_kw=250.0)
    insere_lectures(connexion_ml, site_id, heures=3, fin=ANCRAGE)

    frame = load_from_database(connexion_ml)

    mien = frame[frame["site_id"] == site_id]
    assert len(mien) == 3
    assert set(mien["site_type"]) == {"factory"}
    assert set(mien["capacity_kw"]) == {250.0}


def test_load_recent_from_database_excludes_readings_before_the_since_bound(
    connexion_ml: Connection,
) -> None:
    site_id = insere_site(connexion_ml)
    insere_lectures(connexion_ml, site_id, heures=5, fin=ANCRAGE)

    frame = load_recent_from_database(
        connexion_ml, since=ANCRAGE - timedelta(hours=2), until=ANCRAGE
    )

    assert list(frame["timestamp"]) == [
        ANCRAGE - timedelta(hours=2),
        ANCRAGE - timedelta(hours=1),
        ANCRAGE,
    ]


def test_load_recent_from_database_includes_a_reading_exactly_at_the_since_bound(
    connexion_ml: Connection,
) -> None:
    site_id = insere_site(connexion_ml)
    insere_lecture(connexion_ml, site_id, instant=ANCRAGE)

    frame = load_recent_from_database(
        connexion_ml, since=ANCRAGE, until=ANCRAGE + timedelta(hours=3)
    )

    assert len(frame) == 1


def test_load_recent_from_database_keeps_timestamps_timezone_aware(
    connexion_ml: Connection,
) -> None:
    site_id = insere_site(connexion_ml)
    insere_lecture(connexion_ml, site_id, instant=ANCRAGE)

    frame = load_recent_from_database(
        connexion_ml, since=ANCRAGE, until=ANCRAGE + timedelta(hours=3)
    )

    assert frame["timestamp"].dt.tz is not None


def test_load_recent_from_database_orders_readings_by_site_then_timestamp(
    connexion_ml: Connection,
) -> None:
    site_id = insere_site(connexion_ml)
    for decalage in (2, 0, 1):
        insere_lecture(connexion_ml, site_id, instant=ANCRAGE + timedelta(hours=decalage))

    frame = load_recent_from_database(
        connexion_ml, since=ANCRAGE, until=ANCRAGE + timedelta(hours=3)
    )

    assert list(frame["timestamp"]) == [
        ANCRAGE,
        ANCRAGE + timedelta(hours=1),
        ANCRAGE + timedelta(hours=2),
    ]


def test_load_recent_from_database_returns_the_contract_columns_even_without_any_row(
    connexion_ml: Connection,
) -> None:
    frame = load_recent_from_database(
        connexion_ml, since=ANCRAGE + timedelta(days=365), until=ANCRAGE + timedelta(days=400)
    )

    assert frame.empty
    assert list(frame.columns) == OUTPUT_COLUMNS


def test_load_recent_from_database_types_a_fully_null_capacity_kw_as_float64(
    connexion_ml: Connection,
) -> None:
    site_id = insere_site(connexion_ml, capacity_kw=None)
    insere_lectures(connexion_ml, site_id, heures=3, fin=ANCRAGE)

    frame = load_recent_from_database(
        connexion_ml, since=ANCRAGE - timedelta(hours=2), until=ANCRAGE
    )

    assert frame["capacity_kw"].dtype == "float64"
    assert frame["capacity_kw"].isna().all()


def test_load_recent_from_database_types_a_null_is_working_hours_as_float64(
    connexion_ml: Connection,
) -> None:
    site_id = insere_site(connexion_ml)
    insere_lecture(connexion_ml, site_id, instant=ANCRAGE, is_working_hours=None)
    insere_lecture(
        connexion_ml, site_id, instant=ANCRAGE + timedelta(hours=1), is_working_hours=True
    )

    frame = load_recent_from_database(
        connexion_ml, since=ANCRAGE, until=ANCRAGE + timedelta(hours=3)
    )

    assert frame["is_working_hours"].dtype == "float64"
    assert list(frame["is_working_hours"].isna()) == [True, False]


def test_load_recent_from_database_types_is_working_hours_as_float64_even_without_a_null(
    connexion_ml: Connection,
) -> None:
    # Sans cette garantie, le dtype dependrait du contenu de la fenetre lue : `bool` ici, `float64`
    # des qu'une seule lecture est a NULL, et le schema des deux chargeurs cesserait d'etre egal.
    site_id = insere_site(connexion_ml)
    insere_lectures(connexion_ml, site_id, heures=2, fin=ANCRAGE)

    frame = load_recent_from_database(
        connexion_ml, since=ANCRAGE - timedelta(hours=2), until=ANCRAGE
    )

    assert frame["is_working_hours"].dtype == "float64"


def test_both_loaders_produce_the_same_columns_in_the_same_order(
    connexion_ml: Connection, tmp_path: Path
) -> None:
    site_id = insere_site(connexion_ml)
    insere_lectures(connexion_ml, site_id, heures=2, fin=ANCRAGE)
    csv_path = tmp_path / "lectures.csv"
    pd.DataFrame(
        {
            "site_id": [site_id],
            "timestamp": [ANCRAGE],
            "consumption_kwh": [50.0],
            "temperature_celsius": [15.0],
            "humidity_percent": [50.0],
            "solar_irradiance_wm2": [0.0],
            "is_working_hours": [True],
            "site_type": ["office"],
        }
    ).to_csv(csv_path, index=False)

    depuis_la_base = load_recent_from_database(
        connexion_ml, since=ANCRAGE - timedelta(hours=1), until=ANCRAGE
    )
    depuis_le_csv = load_from_csv(csv_path)

    assert list(depuis_la_base.columns) == list(depuis_le_csv.columns)
    assert depuis_la_base.dtypes.to_dict() == depuis_le_csv.dtypes.to_dict()


def test_load_recent_from_database_excludes_readings_after_the_until_bound(
    connexion_ml: Connection,
) -> None:
    site_id = insere_site(connexion_ml)
    insere_lectures(connexion_ml, site_id, heures=5, fin=ANCRAGE + timedelta(hours=4))

    frame = load_recent_from_database(
        connexion_ml, since=ANCRAGE - timedelta(days=1), until=ANCRAGE
    )

    assert list(frame["timestamp"]) == [ANCRAGE]
