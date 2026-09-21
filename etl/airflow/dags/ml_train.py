"""DAG d'entrainement du modele LightGBM (issue #115).

Pas de planification : reentrainer est couteux et sa cadence n'est pas une decision prise, en
particulier tant que `train.py` ecrase le modele sans comparer ses metriques a l'ancien (cf.
`docs/architecture/10-infra.md`, section Airflow). Declenchement manuel depuis l'UI ou la CLI
Airflow en attendant. `ml_score` (DAG separe, planifie toutes les heures) reutilise le modele que
ce DAG ecrit, il ne reentraine jamais rien lui-meme.
"""

from __future__ import annotations

from datetime import datetime, timedelta

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
    # Deux entrainements simultanes ecriraient le meme fichier modele.
    max_active_runs=1,
    tags=["ml"],
) as dag:
    # `--no-sync` : l'environnement `/opt/ml/.venv` est fige a la construction de l'image, `uv run`
    # ne le resynchronise pas (sinon `enervision-ml` est reconstruit a chaque tache).
    # `env -u VIRTUAL_ENV` : l'image de base positionne celui d'Airflow, que `uv` signale a chaque
    # execution sans qu'il change quoi que ce soit.
    BashOperator(
        task_id="train",
        bash_command=(
            "cd /opt/ml && env -u VIRTUAL_ENV uv run --no-sync python -m enervision_ml.train "
            f"--model-output {MODEL_PATH} --mlflow-tracking-uri {MLFLOW_TRACKING_URI}"
        ),
        # Un entrainement complet dure quelques minutes ; une connexion pendue ne doit pas
        # immobiliser un slot du scheduler indefiniment.
        execution_timeout=timedelta(hours=1),
    )
