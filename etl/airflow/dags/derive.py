"""DAG de surveillance de la dérive du modèle de prévision (issue #45).

Quotidien, pas horaire : la fenêtre mesurée couvre 168 h, la recalculer chaque heure écrirait
vingt-quatre lignes presque identiques par jour et se heurterait à l'index d'idempotence
`uq_drift_report_window`. Planifié après les scorings de la nuit, et décalé de `ml_score` (à
l'heure pile) comme de `alertes` (à la quinzième minute).

Tâche distincte du DAG `alertes` plutôt qu'ajoutée à lui : un échec de dérive y ferait croire
que la détection d'alertes a échoué, et ce DAG porte un budget temporel déjà argumenté face à
son pas horaire.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

# Le backend a son propre environnement uv dans l'image (ADR 0008). `--no-sync` et
# `env -u VIRTUAL_ENV` : cf. `ml_train.py`, même raisonnement.
COMMANDE_BACKEND = "cd /opt/backend && env -u VIRTUAL_ENV uv run --no-sync python -m"

# Piège : aucune reprise. Une dérive n'est pas un échec transitoire, la rejouer la redéclarerait
# à l'identique ; et la cadence quotidienne pardonne une connexion perdue.
TENTATIVES = 0
PLAFOND = timedelta(minutes=10)

with DAG(
    dag_id="derive",
    description=(
        "Compare les prévisions déjà écrites aux lectures réellement arrivées "
        "(app.monitoring.drift)."
    ),
    schedule="30 5 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["ml", "monitoring"],
) as dag:
    BashOperator(
        task_id="derive",
        bash_command=f"{COMMANDE_BACKEND} app.monitoring.drift",
        retries=TENTATIVES,
        execution_timeout=PLAFOND,
    )
