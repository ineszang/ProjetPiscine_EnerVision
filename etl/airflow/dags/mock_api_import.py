"""DAG d'import périodique des données de l'API Mock EnerVision (issue #15).

Orchestre le pipeline existant `app.etl.mock_api_import` sans dupliquer sa logique ETL.
Chaque exécution traite l'intervalle horaire Airflow précédent.

Le pipeline backend reste responsable de la validation, de la normalisation, du suivi de la
qualité, de l'idempotence et du chargement dans PostgreSQL/TimescaleDB.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

# Le backend possède son propre environnement uv dans l'image Airflow (ADR 0008).
COMMANDE_BACKEND = "cd /opt/backend && env -u VIRTUAL_ENV uv run --no-sync python -m"

# L'API et le pipeline backend plafonnent une réponse à 1 000 lectures par site.
LIMITE_LECTURES = 60

# Deux reprises donnent trois tentatives au total. Même dans le pire cas, l'exécution reste
# inférieure au pas horaire du DAG.
NOMBRE_REPRISES = 2
DELAI_ENTRE_REPRISES = timedelta(minutes=2)
PLAFOND_PAR_TENTATIVE = timedelta(minutes=10)

with DAG(
    dag_id="mock_api_import",
    description="Importe chaque heure les données de l'API Mock dans site et reading.",
    schedule="@hourly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    # Deux exécutions simultanées pourraient demander et traiter le même intervalle.
    max_active_runs=1,
    tags=["etl", "mock-api"],
) as dag:
    BashOperator(
        task_id="import_mock_api",
        bash_command=(
            f"{COMMANDE_BACKEND} app.etl.mock_api_import "
            '--start-time "{{ data_interval_start.isoformat() }}" '
            '--end-time "{{ data_interval_end.isoformat() }}" '
            f"--limit {LIMITE_LECTURES}"
        ),
        retries=NOMBRE_REPRISES,
        retry_delay=DELAI_ENTRE_REPRISES,
        execution_timeout=PLAFOND_PAR_TENTATIVE,
    )
