import pandas as pd

from enervision_ml.baseline import SEASONAL_LAG_COLUMN, seasonal_persistence_predictions


def test_seasonal_persistence_predictions_returns_the_168h_lag_column() -> None:
    features = pd.DataFrame({SEASONAL_LAG_COLUMN: [1.0, 2.0, 3.0], "autre_colonne": [9, 9, 9]})

    predictions = seasonal_persistence_predictions(features)

    assert predictions.tolist() == [1.0, 2.0, 3.0]
