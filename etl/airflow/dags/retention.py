"""DAG de rétention de l'hypertable `reading` : export vers Garage puis suppression (issue #36).

La nuit, parce que `drop_chunks` pose un verrou exclusif sur `reading`, `site` et `dataset`
jusqu'au COMMIT : un chunk est supprimé dans une transaction courte, mais hors des heures où
l'API et les DAGs horaires écrivent. À :20 pour se glisser entre `ml_score` (à l'heure pile),
`alertes` (à :15) et `mock_api_import` (à :45), bien avant `derive` (05:30). Une reprise est sans
risque : le module est idempotent, un objet déjà exporté avec le même sha256 n'est pas réécrit et
un chunk déjà supprimé n'est plus éligible. La borne vient de `APP_READING_RETENTION_DAYS`
(1095 jours), posée par le compose sur `airflow-scheduler` avec les réglages `APP_S3_*`.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

# Le backend a son propre environnement uv dans l'image (ADR 0008). `--no-sync` et
# `env -u VIRTUAL_ENV` : cf. `ml_train.py`, même raisonnement.
COMMANDE_BACKEND = "cd /opt/backend && env -u VIRTUAL_ENV uv run --no-sync python -m"

TENTATIVES = 1
DELAI_ENTRE_TENTATIVES = timedelta(minutes=5)
PLAFOND = timedelta(minutes=20)

with DAG(
    dag_id="retention",
    description=(
        "Exporte vers Garage puis supprime les chunks de reading plus vieux que la borne de "
        "rétention (app.etl.reading_retention)."
    ),
    schedule="20 3 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["etl", "retention"],
) as dag:
    BashOperator(
        task_id="archiver",
        bash_command=f"{COMMANDE_BACKEND} app.etl.reading_retention",
        retries=TENTATIVES,
        retry_delay=DELAI_ENTRE_TENTATIVES,
        execution_timeout=PLAFOND,
    )
