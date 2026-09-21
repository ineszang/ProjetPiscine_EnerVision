"""Entrainement du modele LightGBM de prevision de consommation energetique.

CLI autonome, sur le meme gabarit que `apps/backend/app/etl/historical_import.py`
(argparse, connexion directe a la base). Cf. `docs/ML-START.md`, section 1.

    uv run python -m enervision_ml.train --csv ../ml/data/all_sites_combined.csv
    uv run python -m enervision_ml.train  # lit ML_DATABASE_URL

Le modele entraine est ecrit en fichier (`Booster.save_model()`) et suivi par MLflow (parametres,
metriques, artefact). La base ne stocke jamais le modele lui-meme, seulement une reference vers
lui (`prediction.model_reference`, pose par le futur service de scoring - hors perimetre ici).
"""

import argparse
from pathlib import Path
from typing import Any

import lightgbm as lgb
import mlflow
import mlflow.lightgbm
import pandas as pd
from sqlalchemy import create_engine

from enervision_ml import config
from enervision_ml.baseline import seasonal_persistence_predictions
from enervision_ml.data import load_from_csv, load_from_database
from enervision_ml.features import TARGET_COLUMN, build_features, feature_columns
from enervision_ml.metrics import regression_metrics

CATEGORICAL_FEATURES = ["site_type"]

LIGHTGBM_PARAMS: dict[str, Any] = {
    "objective": "regression",
    "metric": "mae",
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_data_in_leaf": 50,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "verbosity": -1,
}

NUM_BOOST_ROUND = 1000
EARLY_STOPPING_ROUNDS = 50
DEFAULT_TEST_FRACTION = 0.15


def load_raw_frame(csv_path: Path | None) -> pd.DataFrame:
    """Lit les lectures brutes, depuis le CSV de demarrage ou depuis PostgreSQL."""
    if csv_path is not None:
        return load_from_csv(csv_path)

    engine = create_engine(config.database_url())
    try:
        return load_from_database(engine)
    finally:
        engine.dispose()


def chronological_split(
    features: pd.DataFrame, test_fraction: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Coupe par date de coupure, jamais par tirage aleatoire de lignes.

    Une coupure aleatoire laisserait des lignes d'apres la coupure "voir" des lignes d'avant via
    leurs lags/moyennes glissantes, une fuite qui masquerait un surapprentissage a l'evaluation.
    """
    coupure = features["timestamp"].quantile(1 - test_fraction)
    entrainement = features[features["timestamp"] < coupure]
    validation = features[features["timestamp"] >= coupure]
    return entrainement, validation


def prepare_dataset(frame: pd.DataFrame, columns: list[str]) -> tuple[pd.DataFrame, pd.Series]:
    typee = frame.copy()
    typee["site_type"] = typee["site_type"].astype("category")
    return typee[columns], typee[TARGET_COLUMN]


def train(
    *,
    csv_path: Path | None,
    model_output: Path,
    test_fraction: float = DEFAULT_TEST_FRACTION,
    tracking_uri: str | None = None,
) -> tuple[dict[str, float], dict[str, float]]:
    """Execute le pipeline complet et rend (metriques du modele, metriques de la baseline)."""
    raw = load_raw_frame(csv_path)
    features = build_features(raw)
    columns = feature_columns()

    # Les premieres 168h par site n'ont pas de lag hebdomadaire complet : ni entrainables, ni
    # comparables a la baseline saisonniere qui en depend.
    utilisable = features.dropna(subset=[TARGET_COLUMN, f"{TARGET_COLUMN}_lag_168h"])

    entrainement, validation = chronological_split(utilisable, test_fraction)
    if entrainement.empty or validation.empty:
        raise ValueError(
            "Fenetre d'entrainement ou de validation vide : jeu de donnees trop court pour "
            f"test_fraction={test_fraction}."
        )

    X_train, y_train = prepare_dataset(entrainement, columns)
    X_valid, y_valid = prepare_dataset(validation, columns)

    train_set = lgb.Dataset(
        X_train,
        label=y_train,
        categorical_feature=CATEGORICAL_FEATURES,
        free_raw_data=False,
    )
    valid_set = lgb.Dataset(
        X_valid,
        label=y_valid,
        reference=train_set,
        categorical_feature=CATEGORICAL_FEATURES,
        free_raw_data=False,
    )

    booster = lgb.train(
        LIGHTGBM_PARAMS,
        train_set,
        num_boost_round=NUM_BOOST_ROUND,
        valid_sets=[valid_set],
        callbacks=[
            lgb.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False),
            lgb.log_evaluation(period=0),
        ],
    )

    predictions = pd.Series(
        booster.predict(X_valid, num_iteration=booster.best_iteration),
        index=X_valid.index,
    )
    model_metrics = regression_metrics(y_valid, predictions)
    baseline_metrics = regression_metrics(y_valid, seasonal_persistence_predictions(validation))

    model_output.parent.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(model_output))

    _log_to_mlflow(
        tracking_uri=tracking_uri,
        booster=booster,
        model_metrics=model_metrics,
        baseline_metrics=baseline_metrics,
        n_train=len(X_train),
        n_valid=len(X_valid),
        test_fraction=test_fraction,
        model_output=model_output,
    )

    return model_metrics, baseline_metrics


def _log_to_mlflow(
    *,
    tracking_uri: str | None,
    booster: lgb.Booster,
    model_metrics: dict[str, float],
    baseline_metrics: dict[str, float],
    n_train: int,
    n_valid: int,
    test_fraction: float,
    model_output: Path,
) -> None:
    uri = tracking_uri or config.mlflow_tracking_uri()
    if uri is not None:
        mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(config.MLFLOW_EXPERIMENT_NAME)

    with mlflow.start_run():
        mlflow.log_params(
            {
                **LIGHTGBM_PARAMS,
                "num_boost_round": booster.best_iteration or NUM_BOOST_ROUND,
                "test_fraction": test_fraction,
                "n_train": n_train,
                "n_valid": n_valid,
            }
        )
        mlflow.log_metrics({f"model_{cle}": valeur for cle, valeur in model_metrics.items()})
        mlflow.log_metrics({f"baseline_{cle}": valeur for cle, valeur in baseline_metrics.items()})
        mlflow.lightgbm.log_model(booster, name="model")
        mlflow.log_artifact(str(model_output))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Entrainement du modele LightGBM EnerVision")

    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help=(
            "Chemin vers le CSV historique (chemin de demarrage). Omis, lit ML_DATABASE_URL "
            "et se connecte directement a PostgreSQL (reading + site)."
        ),
    )
    parser.add_argument(
        "--model-output",
        type=Path,
        default=Path("models/lightgbm-consumption.txt"),
        help="Chemin d'ecriture du modele entraine. Defaut : models/lightgbm-consumption.txt.",
    )
    parser.add_argument(
        "--test-fraction",
        type=float,
        default=DEFAULT_TEST_FRACTION,
        help=(
            "Part la plus recente de l'historique reservee a la validation. "
            f"Defaut : {DEFAULT_TEST_FRACTION}."
        ),
    )
    parser.add_argument(
        "--mlflow-tracking-uri",
        default=None,
        help="Surcharge MLFLOW_TRACKING_URI. Omis, magasin SQLite local (./mlflow.db).",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    model_metrics, baseline_metrics = train(
        csv_path=args.csv,
        model_output=args.model_output,
        test_fraction=args.test_fraction,
        tracking_uri=args.mlflow_tracking_uri,
    )

    print("Modele LightGBM :", model_metrics)
    print("Baseline saisonniere (t-168h) :", baseline_metrics)

    if model_metrics["mae"] < baseline_metrics["mae"]:
        gain = (1 - model_metrics["mae"] / baseline_metrics["mae"]) * 100
        print(f"LightGBM bat la baseline de {gain:.1f}% de MAE.")
    else:
        print("LightGBM ne bat pas la baseline saisonniere sur ce decoupage.")


if __name__ == "__main__":
    main()
