"""DAG de scoring horaire du modele LightGBM (issue #115).

Planifie toutes les heures, au rythme documente par `enervision_ml.score` (score le prochain pas
horaire par site). Reutilise le modele ecrit par `ml_train` (DAG separe, declenche a la main) :
ce DAG ne reentraine jamais rien. Si aucun modele n'a encore ete entraine, la tache echoue
(`FileNotFoundError`) plutot que de rester silencieuse.
"""

from __future__ import annotations

from datetime import datetime

from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator

MODEL_PATH = "/opt/ml/state/models/lightgbm-consumption.txt"

with DAG(
    dag_id="ml_score",
    description="Score le prochain pas horaire par site (enervision_ml.score).",
    schedule="@hourly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["ml"],
) as dag:
    # `--frozen --no-dev` : cf. `ml_train.py`, meme raisonnement.
    BashOperator(
        task_id="score",
        bash_command=(
            "cd /opt/ml && uv run --frozen --no-dev python -m enervision_ml.score "
            f"--model {MODEL_PATH}"
        ),
    )
