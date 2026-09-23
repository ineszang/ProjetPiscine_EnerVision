"""DAG d'import périodique des données de l'API Mock EnerVision (issue #15).

Orchestre le pipeline existant `app.etl.mock_api_import` sans dupliquer sa logique ETL.
Chaque exécution traite l'heure précédant son déclenchement.

Le pipeline backend reste responsable de la validation, de la normalisation, du suivi de la
qualité, de l'idempotence et du chargement dans PostgreSQL/TimescaleDB.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG
from airflow.timetables.trigger import CronTriggerTimetable

# Le backend possède son propre environnement uv dans l'image Airflow (ADR 0008).
COMMANDE_BACKEND = "cd /opt/backend && env -u VIRTUAL_ENV uv run --no-sync python -m"

# Deux reprises donnent trois tentatives au total. Même dans le pire cas, l'exécution reste
# inférieure au pas horaire du DAG.
NOMBRE_REPRISES = 2
DELAI_ENTRE_REPRISES = timedelta(minutes=2)
PLAFOND_PAR_TENTATIVE = timedelta(minutes=10)

# L'intervalle est déclaré explicitement pour ne pas dépendre de la valeur du paramètre Airflow
# `create_cron_data_intervals`. Le déclenchement à :45 laisse quinze minutes avant `ml_score`,
# exécuté à l'heure pile, puis avant `alertes`, exécuté à :15. Conséquence vérifiée empiriquement
# sur l'API Mock (cf. `limit_for_window()` dans `app.etl.mock_api_import`) : la fenêtre importée
# est `[:45, :45)`, donc chaque lecture atterrit à :45, pas à :00, un décalage constant sur
# toute la série, sans effet sur les lags positionnels ni sur les jointures en aval (`ml_score`
# vise la dernière lecture + 1h, `derive` joint à l'égalité), cf. 40-data.md.
PLANIFICATION = CronTriggerTimetable(
    "45 * * * *",
    timezone="UTC",
    interval=timedelta(hours=1),
)

with DAG(
    dag_id="mock_api_import",
    description="Importe chaque heure les données de l'API Mock dans site et reading.",
    schedule=PLANIFICATION,
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
            "--start-time \"{{ data_interval_start.strftime('%Y-%m-%dT%H:%M:%S') }}\" "
            "--end-time \"{{ data_interval_end.strftime('%Y-%m-%dT%H:%M:%S') }}\""
            # Pas de --limit : app.etl.mock_api_import.limit_for_window() le dérive de la
            # fenêtre (une lecture/heure), et refuse une fenêtre qui ne couvre pas un nombre
            # entier d'heures ou dépasse le plafond de l'API. Porter la règle dans le code,
            # pas dans ce DAG, évite qu'un appel manuel oublie de la respecter.
        ),
        retries=NOMBRE_REPRISES,
        retry_delay=DELAI_ENTRE_REPRISES,
        execution_timeout=PLAFOND_PAR_TENTATIVE,
    )
