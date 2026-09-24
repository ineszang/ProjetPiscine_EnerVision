# 70 · Pilotage des traitements automatisés

Ce document dit à l'opérateur quoi surveiller, comment lire ce qu'il voit et quoi faire quand un
traitement déraille. Il ne redit pas le fonctionnement : la table des DAGs vit dans
[10-infra.md](10-infra.md), la chaîne de données dans [40-data.md](40-data.md), la dérive dans
l'[ADR 0013](../adr/0013-surveillance-de-derive-dans-le-backend.md), la rétention dans
l'[ADR 0019](../adr/0019-stockage-objet-garage-et-cycle-de-vie-des-mesures.md), la supervision
dans [60-observabilite.md](60-observabilite.md).

## Carte des traitements

Les planifications sont en **UTC** : Airflow n'a pas de fuseau configuré. En heure de Paris
l'été, ajouter deux heures.

| DAG | Planification (UTC) | Ce qu'il fait | Même traitement à la main |
|---|---|---|---|
| `mock_api_import` | chaque heure à :45 | importe la mesure de l'heure pile de l'API Mock, une par site | `python -m app.etl.mock_api_import --start-time … --end-time …` |
| `ml_score` | chaque heure pile | score le pas horaire suivant, écrit `prediction` | `make ml-score` |
| `alertes` | chaque heure à :15 | détecte les alertes internes, puis génère les recommandations | `make detect-alerts`, puis `make recommendations` |
| `retention` | 03:20 | exporte vers Garage les chunks de `reading` de plus de 1 095 jours, puis les supprime | `python -m app.etl.reading_retention` |
| `derive` | 05:30 | calcule le rapport de dérive du modèle sur 168 h | `python -m app.monitoring.drift` |
| `ml_train` | manuel | réentraîne LightGBM et **écrase** le modèle | `make ml-train` |
| `historical_import` | manuel | importe le jeu historique CSV | `python -m app.etl.historical_import --csv … --metadata …` |

Les modules `app.*` se lancent depuis `apps/backend` (`uv run python -m …`). Tous les DAGs ont
`max_active_runs=1` et `catchup=False` : un retard ne rejoue pas les heures manquées.

## Où regarder

Sur la machine, chaque environnement vit dans `/srv/enervision/<env>` et n'écoute que sur la
boucle locale : on y accède par tunnel SSH.

| Quoi | Production | Recette | Dev |
|---|---|---|---|
| Interface Airflow | `127.0.0.1:8080` | `127.0.0.1:8082` | `127.0.0.1:8084` |
| Grafana (production seulement) | `127.0.0.1:3001` | - | - |
| Mailpit, où arrivent les alertes | `127.0.0.1:8025` | `127.0.0.1:8026` | `127.0.0.1:8027` |

```bash
ssh -L 8080:127.0.0.1:8080 -L 3001:127.0.0.1:3001 -L 8025:127.0.0.1:8025 root@<IP-VM-G3>
```

En ligne de commande, depuis `/srv/enervision/<env>` :

```bash
compose="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
$compose exec airflow-apiserver airflow dags list-runs derive     # derniers passages
$compose exec airflow-apiserver airflow dags trigger ml_train      # lancement manuel
$compose logs --tail=100 airflow-scheduler                         # les tâches tournent ici
```

**Aucune alerte ne signale l'échec d'un DAG** ([60-observabilite.md](60-observabilite.md)) :
un coup d'œil quotidien à l'interface Airflow reste nécessaire.

## Lire le rapport de dérive

`GET /api/v1/monitoring/drift` (rôle `operateur`) rend le dernier rapport par site et une ligne
globale. Le verdict suit cet ordre (`app/services/drift.py`) :

| Verdict | Condition | Ce que ça veut dire | Quoi faire |
|---|---|---|---|
| `indetermine` | moins de 24 prévisions vérifiées sur la fenêtre | pas assez de recul pour conclure | attendre ; si ça dure, vérifier `ml_score` |
| `derive`, couverture | moins de 80 % des prévisions ont trouvé leur mesure réelle | **le pipeline**, pas le modèle | vérifier `mock_api_import` et `ml_score` dans Airflow |
| `derive`, erreur | MAE au-delà de 1,25 fois celle de la fenêtre de référence | le modèle se trompe plus qu'avant | réentraîner (ci-dessous) |
| `derive`, biais | biais absolu au-delà du seuil, désactivé par défaut | le modèle se trompe toujours du même côté | réentraîner, après en avoir cherché la cause dans les données |
| `stable` | aucune des conditions précédentes | rien à faire | - |

## Réentraîner sans perdre le modèle en service

`ml_train` reste manuel parce que `train.py` écrase le modèle sans comparer ses métriques à
celles de l'ancien ([10-infra.md](10-infra.md)). Garder une copie avant de lancer :

```bash
$compose exec airflow-scheduler cp /opt/ml/state/models/lightgbm-consumption.txt \
  /opt/ml/state/models/lightgbm-consumption.txt.avant
$compose exec airflow-apiserver airflow dags trigger ml_train
```

Comparer ensuite les métriques des deux derniers runs, que `train.py` enregistre dans le magasin
MLflow du volume (`/opt/ml/state/mlflow.db`). Aucune interface MLflow n'est servie sur la
machine : `ml/README.md` décrit `mlflow ui`. Si le nouveau modèle est moins bon, remettre la
copie en place : le prochain `ml_score` l'utilisera.

## Rétention et archives

`retention` supprime de la base les chunks de `reading` plus vieux que
`APP_READING_RETENTION_DAYS` (1 095 jours), **après** les avoir exportés en CSV gzip dans le
bucket Garage de l'environnement, chiffrés en SSE-C. Il est idempotent : une reprise ne réécrit
pas un objet déjà exporté et ne retrouve plus un chunk déjà supprimé.

- **La clé `GARAGE_SSE_KEY` du `.env` est la seule qui déchiffre les archives.** Garage ne la
  garde pas. Perdue, les archives sont illisibles : elle se sauvegarde hors de la machine.
- Restaurer un chunk : `get_object` avec la clé SSE-C, `gunzip`, puis
  `COPY reading FROM STDIN CSV HEADER`. La contrainte `uq_reading_source` refuse les doublons
  ([ADR 0019](../adr/0019-stockage-objet-garage-et-cycle-de-vie-des-mesures.md)).

## Reprendre après un incident

| Situation | Reprise |
|---|---|
| `mock_api_import` a manqué des heures | relancer à la main avec `--start-time` et `--end-time` sur la fenêtre manquante ; le module refuse toute fenêtre qui recouvre le CSV historique |
| `alertes` a échoué | relancer : les deux tâches sont idempotentes (`ON CONFLICT DO NOTHING`) |
| `derive` a échoué | relancer : un index d'unicité par fenêtre empêche les doublons |
| `retention` a échoué | relancer : idempotent, voir plus haut |
| `ml_score` en échec répété | lire les journaux du scheduler ; deux tentatives et un plafond de 30 minutes par passage |
