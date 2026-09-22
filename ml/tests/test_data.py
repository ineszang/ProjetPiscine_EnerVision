from pathlib import Path

import pandas as pd
import pytest

from enervision_ml.data import NUMERIC_COLUMNS, load_from_csv

_CSV_HEADER = (
    "site_id,timestamp,consumption_kwh,temperature_celsius,humidity_percent,"
    "solar_irradiance_wm2,is_working_hours,site_type"
)


def write_csv(tmp_path: Path, *lignes: str) -> Path:
    csv_path = tmp_path / "recent.csv"
    csv_path.write_text("\n".join([_CSV_HEADER, *lignes]) + "\n")
    return csv_path


def test_load_from_csv_types_every_numeric_column_as_float(tmp_path: Path) -> None:
    csv_path = write_csv(tmp_path, "SITE001,2026-01-01T00:00:00,10.5,15.0,50.0,0.0,True,office")

    frame = load_from_csv(csv_path)

    for colonne in NUMERIC_COLUMNS:
        assert frame[colonne].dtype == "float64"


def test_load_from_csv_coerces_a_corrupted_measurement_to_nan(tmp_path: Path) -> None:
    # Reproduit une valeur de capteur corrompue plutot que vraiment manquante : `pandas` type
    # alors la colonne entiere en `object`, pas en `float64` rempli de `NaN` -- le meme genre de
    # divergence de typage que celle que `pd.read_sql` produit sur une colonne SQL entierement
    # `NULL` (cf. `site.capacity_kw`, jamais peuplee par aucun pipeline d'ingestion aujourd'hui).
    csv_path = write_csv(
        tmp_path,
        "SITE001,2026-01-01T00:00:00,10.5,15.0,50.0,0.0,True,office",
        "SITE001,2026-01-01T01:00:00,capteur_hs,15.2,50.5,0.0,True,office",
    )

    frame = load_from_csv(csv_path)

    assert frame["consumption_kwh"].dtype == "float64"
    assert frame["consumption_kwh"].iloc[0] == 10.5
    assert pd.isna(frame["consumption_kwh"].iloc[1])


def test_load_from_csv_always_types_capacity_kw_as_float(tmp_path: Path) -> None:
    # `capacity_kw` n'existe pas dans ce CSV : `load_from_csv` la pose elle-meme a `NaN`. Cette
    # affectation directe est deja un `float`, contrairement au cas `pd.read_sql` -- ce test
    # garde le contrat visible malgre tout, au cas ou l'implementation changerait.
    csv_path = write_csv(tmp_path, "SITE001,2026-01-01T00:00:00,10.5,15.0,50.0,0.0,True,office")

    frame = load_from_csv(csv_path)

    assert frame["capacity_kw"].dtype == "float64"
    assert pd.isna(frame["capacity_kw"].iloc[0])


@pytest.mark.parametrize("present", ["1", "True"], ids=["entier", "booleen_textuel"])
def test_load_from_csv_keeps_a_missing_is_working_hours_as_nan(
    tmp_path: Path, present: str
) -> None:
    # Une case vide vaut "on ne sait pas", que LightGBM sait traiter. La rendre `True` inventerait
    # une heure ouvree, et le modele apprendrait sur une valeur que personne n'a mesuree.
    csv_path = write_csv(
        tmp_path,
        f"SITE001,2026-01-01T00:00:00,10.5,15.0,50.0,0.0,{present},office",
        "SITE001,2026-01-01T01:00:00,11.5,15.2,50.5,0.0,,office",
    )

    frame = load_from_csv(csv_path)

    assert frame["is_working_hours"].iloc[0] == 1
    assert pd.isna(frame["is_working_hours"].iloc[1])


@pytest.mark.parametrize(
    "valeurs",
    [("1", "0"), ("True", "False")],
    ids=["entier", "booleen_textuel"],
)
def test_load_from_csv_always_types_is_working_hours_as_float(
    tmp_path: Path, valeurs: tuple[str, str]
) -> None:
    # Le dtype ne doit pas dependre de l'ecriture du fichier ni de la presence d'un trou : c'est
    # ce qui rend comparable le schema des deux chargeurs, cf. `test_data_integration.py`.
    present, absent = valeurs
    csv_path = write_csv(
        tmp_path,
        f"SITE001,2026-01-01T00:00:00,10.5,15.0,50.0,0.0,{present},office",
        f"SITE001,2026-01-01T01:00:00,11.5,15.2,50.5,0.0,{absent},office",
    )

    frame = load_from_csv(csv_path)

    assert frame["is_working_hours"].dtype == "float64"
    assert list(frame["is_working_hours"]) == [1.0, 0.0]
