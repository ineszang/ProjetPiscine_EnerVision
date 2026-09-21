"""DAG d'import du dataset historique EnerVision (issue #119).

Orchestre le pipeline existant `app.etl.historical_import` sans dupliquer sa logique ETL.
Le dataset historique sert à initialiser l'environnement : le DAG reste donc manuel.

Le backend est exécuté dans l'environnement `/opt/backend` embarqué dans l'image Airflow,
sur le même patron que le DAG `alertes` (ADR 0008).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator

COMMANDE_BACKEND = "cd /opt/backend && env -u VIRTUAL_ENV uv run --no-sync python -m"

CSV_PATH = "/opt/data/raw/all_sites_combined.csv"
METADATA_PATH = "/opt/data/raw/dataset_metadata.json"

with DAG(
    dag_id="historical_import",
    description="Importe le dataset historique CSV/JSON dans dataset, site et reading.",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["etl", "historical"],
) as dag:
    BashOperator(
        task_id="import_historical",
        bash_command=(
            f"{COMMANDE_BACKEND} app.etl.historical_import "
            f"--csv {CSV_PATH} "
            f"--metadata {METADATA_PATH} "
            "--source-timezone UTC "
            "--batch-size 1000"
        ),
        retries=1,
        retry_delay=timedelta(minutes=2),
        execution_timeout=timedelta(minutes=30),
    )
