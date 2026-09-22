"""DAG de scoring horaire du modele LightGBM (issue #115).

Planifie toutes les heures, au rythme documente par `enervision_ml.score` (score le prochain pas
horaire par site). Reutilise le modele ecrit par `ml_train` (DAG separe, declenche a la main) :
ce DAG ne reentraine jamais rien. Si aucun modele n'a encore ete entraine, la tache echoue
(`FileNotFoundError`) plutot que de rester silencieuse.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

MODEL_PATH = "/opt/ml/state/models/lightgbm-consumption.txt"

with DAG(
    dag_id="ml_score",
    description="Score le prochain pas horaire par site (enervision_ml.score).",
    schedule="@hourly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    # Deux scorings qui se chevauchent inseraient en meme temps dans `prediction` (pas de contrainte
    # d'unicite sur `(site_id, target_at)`, chaque run garde sa ligne).
    max_active_runs=1,
    tags=["ml"],
) as dag:
    # `--no-sync`, `env -u VIRTUAL_ENV` : cf. `ml_train.py`, meme raisonnement.
    BashOperator(
        task_id="score",
        bash_command=(
            "cd /opt/ml && env -u VIRTUAL_ENV uv run --no-sync python -m enervision_ml.score "
            f"--model {MODEL_PATH}"
        ),
        # Un incident transitoire sur Postgres ne doit pas faire perdre le creneau horaire.
        retries=2,
        retry_delay=timedelta(minutes=2),
        # Bien en dessous du pas horaire : un scoring pendu ne doit pas empieter sur le suivant.
        execution_timeout=timedelta(minutes=30),
    )
