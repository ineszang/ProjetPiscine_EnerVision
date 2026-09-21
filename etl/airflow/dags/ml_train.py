"""DAG d'entrainement du modele LightGBM (issue #115).

Pas de planification : reentrainer est couteux et sa cadence n'est pas une decision prise
(cf. `docs/architecture/20-backend.md`). Declenchement manuel depuis l'UI ou la CLI Airflow en
attendant. `ml_score` (DAG separe, planifie toutes les heures) reutilise le modele que ce DAG
ecrit, il ne reentraine jamais rien lui-meme.
"""

from __future__ import annotations

from datetime import datetime

from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator

MODEL_PATH = "/opt/ml/state/models/lightgbm-consumption.txt"
MLFLOW_TRACKING_URI = "sqlite:////opt/ml/state/mlflow.db"

with DAG(
    dag_id="ml_train",
    description="Entraine le modele LightGBM de prevision de consommation (enervision_ml.train).",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["ml"],
) as dag:
    # `--frozen --no-dev` : l'environnement `/opt/ml/.venv` est fige a la construction de l'image
    # (groupe `dev` exclu). Sans `--no-dev` ici, `uv run` resynchronise ruff/mypy a chaque
    # execution : un acces reseau evitable, sur le chemin d'execution d'une tache planifiee.
    BashOperator(
        task_id="train",
        bash_command=(
            "cd /opt/ml && uv run --frozen --no-dev python -m enervision_ml.train "
            f"--model-output {MODEL_PATH} --mlflow-tracking-uri {MLFLOW_TRACKING_URI}"
        ),
    )
