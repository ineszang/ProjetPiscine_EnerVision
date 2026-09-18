import pandas as pd

from enervision_ml.data import NUMERIC_COLUMNS, OUTPUT_COLUMNS, _typer


def make_frame_with_object_dtype_capacity() -> pd.DataFrame:
    # Reproduit ce que `pd.read_sql` renvoie pour une colonne entierement `NULL` en base :
    # dtype `object` rempli de `None`, pas `float64` rempli de `NaN`.
    frame = pd.DataFrame(
        {colonne: [1.0, 2.0] for colonne in OUTPUT_COLUMNS if colonne not in NUMERIC_COLUMNS}
    )
    for colonne in NUMERIC_COLUMNS:
        frame[colonne] = pd.Series([None, None], dtype="object")
    return frame


def test_typer_coerces_an_all_null_object_column_to_float() -> None:
    frame = make_frame_with_object_dtype_capacity()

    typee = _typer(frame)

    for colonne in NUMERIC_COLUMNS:
        assert typee[colonne].dtype == "float64"
        assert typee[colonne].isna().all()


def test_typer_preserves_real_numeric_values() -> None:
    frame = make_frame_with_object_dtype_capacity()
    frame["capacity_kw"] = pd.Series([100.0, None], dtype="object")

    typee = _typer(frame)

    assert typee["capacity_kw"].tolist()[0] == 100.0
    assert pd.isna(typee["capacity_kw"].tolist()[1])
