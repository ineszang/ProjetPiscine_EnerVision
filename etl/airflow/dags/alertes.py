"""DAG de détection des alertes et de génération des recommandations (issue #116).

Ordonnance ce que `docs/architecture/20-backend.md` et l'ADR 0006 décrivent encore comme lancé à
la main. Toute la logique reste dans `apps/backend`, ce DAG ne fait que l'appeler, sur le patron
de `ml_score` (cf. `docs/architecture/10-infra.md`, section Airflow, et l'ADR 0008 pour
l'environnement `/opt/backend` que l'image embarque désormais).

Planifié à la quinzième minute plutôt qu'à l'heure pile : la règle `anomaly` compare une lecture
à la `prediction` du même instant, que `ml_score` (`@hourly`) vient d'écrire. Aucune dépendance
déclarée entre les deux DAGs pour autant, quatre règles sur cinq ne touchent pas au modèle et un
modèle jamais entraîné ne doit pas priver le parc de ses alertes.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

# Le backend a son propre environnement uv dans l'image (ADR 0008). `--no-sync` et
# `env -u VIRTUAL_ENV` : cf. `ml_train.py`, même raisonnement.
COMMANDE_BACKEND = "cd /opt/backend && env -u VIRTUAL_ENV uv run --no-sync python -m"

# Les deux tâches sont idempotentes en base (`ON CONFLICT DO NOTHING` sur
# `uq_alert_source_reference` et `uq_recommendation_alert_rule`) : reprendre ne duplique rien.
TENTATIVES = 2
DELAI_ENTRE_TENTATIVES = timedelta(minutes=2)
# `execution_timeout` vaut par tentative : c'est le pire cas des deux tâches enchaînées, reprises
# et délais compris, qui doit tenir sous le pas horaire. Les tests d'intégrité en font le calcul.
PLAFOND_PAR_TACHE = timedelta(minutes=5)

with DAG(
    dag_id="alertes",
    description=(
        "Détecte les alertes internes puis génère les recommandations "
        "(app.detection.internal_alerts, app.cli)."
    ),
    schedule="15 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    # Deux exécutions simultanées analyseraient la même fenêtre de 48h, et la génération relit
    # l'intégralité de la table `alert` à chaque passage.
    max_active_runs=1,
    tags=["alertes"],
) as dag:
    detection = BashOperator(
        task_id="detection",
        bash_command=f"{COMMANDE_BACKEND} app.detection.internal_alerts",
        retries=TENTATIVES,
        retry_delay=DELAI_ENTRE_TENTATIVES,
        execution_timeout=PLAFOND_PAR_TACHE,
    )

    recommandations = BashOperator(
        task_id="recommandations",
        bash_command=f"{COMMANDE_BACKEND} app.cli generate-recommendations",
        retries=TENTATIVES,
        retry_delay=DELAI_ENTRE_TENTATIVES,
        execution_timeout=PLAFOND_PAR_TACHE,
    )

    # `recommendation.alert_id` est une clé étrangère `NOT NULL` : la génération n'a rien à lire
    # tant que la détection n'a pas écrit.
    detection >> recommandations
