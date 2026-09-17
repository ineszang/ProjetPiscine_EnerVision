"""Metriques de regression partagees entre le modele et la baseline."""

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, root_mean_squared_error


def regression_metrics(y_true: pd.Series, y_pred: pd.Series) -> dict[str, float]:
    """MAE, RMSE et MAPE (en %), sur les paires non nulles des deux series."""
    valides = y_true.notna() & y_pred.notna()
    reel = y_true[valides]
    predit = y_pred[valides]

    # MAPE diverge a consommation nulle : les mesures a zero (site a l'arret) sont exclues de ce
    # seul ratio, pas des autres metriques.
    non_nul = reel != 0
    mape = float(np.mean(np.abs((reel[non_nul] - predit[non_nul]) / reel[non_nul])) * 100)

    return {
        "mae": float(mean_absolute_error(reel, predit)),
        "rmse": float(root_mean_squared_error(reel, predit)),
        "mape": mape,
        "n_observations": int(valides.sum()),
    }
