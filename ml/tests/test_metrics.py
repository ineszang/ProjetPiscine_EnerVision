import pandas as pd
import pytest

from enervision_ml.metrics import regression_metrics


def test_regression_metrics_computes_mae_and_rmse_on_known_values() -> None:
    y_true = pd.Series([10.0, 20.0, 30.0])
    y_pred = pd.Series([12.0, 18.0, 33.0])

    resultat = regression_metrics(y_true, y_pred)

    assert resultat["mae"] == pytest.approx(7 / 3)
    assert resultat["n_observations"] == 3


def test_regression_metrics_ignores_rows_with_a_missing_value() -> None:
    y_true = pd.Series([10.0, None, 30.0])
    y_pred = pd.Series([12.0, 18.0, None])

    resultat = regression_metrics(y_true, y_pred)

    assert resultat["n_observations"] == 1
    assert resultat["mae"] == 2.0


def test_regression_metrics_excludes_zero_actuals_from_mape_only() -> None:
    y_true = pd.Series([0.0, 10.0])
    y_pred = pd.Series([5.0, 12.0])

    resultat = regression_metrics(y_true, y_pred)

    assert resultat["n_observations"] == 2
    assert resultat["mape"] == pytest.approx(20.0)


def test_metrics_are_zero_for_a_perfect_prediction() -> None:
    y_true = pd.Series([10.0, 20.0])
    y_pred = pd.Series([10.0, 20.0])

    resultat = regression_metrics(y_true, y_pred)

    assert resultat["mae"] == 0.0
    assert resultat["rmse"] == 0.0
    assert resultat["mape"] == 0.0
