# Pipeline ETL — EnerVision

## Objectif

Le pipeline ETL EnerVision permet d'intégrer les données énergétiques dans PostgreSQL/TimescaleDB à partir de deux sources :

- le dataset historique CSV/JSON fourni dans le cadre du projet ;
- l'API Mock EnerVision.

Le pipeline assure :

- l'extraction des données sources ;
- la validation de leur structure et de leur cohérence ;
- la normalisation des données nécessaires au stockage ;
- le suivi de la qualité des données ;
- la traçabilité des données importées ;
- le chargement des données dans PostgreSQL/TimescaleDB ;
- la conservation des valeurs manquantes et des informations de qualité ;
- l'idempotence du chargement afin d'éviter la création de doublons.

## Données sources

### Dataset historique

Le dataset est fourni par le formateur dans le cadre du projet EnerVision.

Il contient les deux fichiers suivants :

```text
all_sites_combined.csv
dataset_metadata.json
```

Ces fichiers sont nécessaires une seule fois pour initialiser les données historiques de l'environnement.

Ils ne sont pas versionnés dans Git. Chaque membre de l'équipe récupère manuellement les fichiers fournis par le formateur et les place dans :

```text
data/raw/
```

Structure locale attendue :

```text
data/
└── raw/
    ├── .gitkeep
    ├── all_sites_combined.csv
    └── dataset_metadata.json
```

Le fichier `.gitkeep` est versionné afin de conserver le répertoire `data/raw/` dans Git. Les fichiers CSV et JSON sont ignorés par Git.

### API Mock

La deuxième source est l'API Mock EnerVision.

Elle permet de récupérer :

- les informations des sites avec `GET /api/v1/sites` ;
- les mesures simulées avec `GET /api/v1/readings`.

L'API Mock est utilisée pour compléter les données historiques avec des mesures simulées récupérées sur une période donnée.

## Technologies utilisées

| Technologie | Utilisation |
|---|---|
| Python | Développement du pipeline ETL |
| Pandas | Lecture, validation et transformation du dataset historique |
| JSON | Lecture des métadonnées et conservation des données sources |
| HTTPX | Appels HTTP asynchrones vers l'API Mock |
| hashlib / SHA-256 | Identification, intégrité et traçabilité du dataset historique |
| SQLAlchemy Async | Connexion et chargement asynchrone en base |
| PostgreSQL | Stockage relationnel |
| TimescaleDB | Stockage des séries temporelles énergétiques |
| Docker Compose | Exécution de l'environnement local |
| Alembic | Gestion des migrations du schéma |
| uv | Gestion et exécution de l'environnement Python |
| Ruff | Contrôle de la qualité du code |
| mypy | Vérification du typage |
| Pytest | Tests automatisés |

## Import du dataset historique

### Fonctionnement du pipeline historique

Le script d'import se trouve dans :

```text
apps/backend/app/etl/historical_import.py
```

Le flux d'import est le suivant :

```text
CSV + métadonnées JSON
          |
          v
      Extraction
          |
          v
      Validation
          |
          v
   Traçabilité SHA-256
          |
          v
     Transformation
          |
          v
 Chargement par batches
          |
          v
PostgreSQL / TimescaleDB
```

#### 1. Extraction

Le pipeline charge :

- `all_sites_combined.csv` avec Pandas ;
- `dataset_metadata.json` avec le module JSON de Python.

#### 2. Validation

Avant toute écriture en base, le pipeline contrôle notamment :

- la présence des colonnes obligatoires ;
- le nombre de lignes ;
- la cohérence des identifiants des sites ;
- la cohérence des informations associées aux sites ;
- les doublons sur le couple `(site_id, timestamp)` ;
- les timestamps ;
- les valeurs manquantes.

Une incohérence détectée pendant cette étape interrompt l'import avant le chargement.

#### 3. Dry-run

Un mode `--dry-run` permet d'exécuter les contrôles sans écrire de données dans PostgreSQL.

Il permet notamment de vérifier :

- le nombre de lignes ;
- le nombre de sites ;
- la période couverte ;
- les doublons ;
- les valeurs NULL ;
- l'empreinte SHA-256.

#### 4. Traçabilité

Une empreinte SHA-256 est calculée à partir du fichier CSV afin d'identifier le dataset utilisé.

Empreinte SHA-256 du dataset validé :

```text
6E3777A97A5660B11855750B9028F70BE72138A11F26795F3A35D9CE74CE0C8D
```

Cette empreinte participe à la traçabilité du dataset chargé.

#### 5. Transformation

Les timestamps sont normalisés avec la timezone :

```text
UTC
```

Le pipeline détermine également la qualité des mesures à partir des données disponibles.

Les valeurs manquantes sont conservées pendant cette phase afin de préserver la donnée source.

Aucune imputation n'est réalisée pendant l'ingestion :

```text
imputed_values = NULL
imputation_method = NULL
```

#### 6. Chargement

Le chargement est réalisé avec SQLAlchemy Async dans PostgreSQL/TimescaleDB.

Les données sont enregistrées dans les tables :

```text
dataset
site
reading
```

Les mesures sont chargées par batches de :

```text
1000 lignes
```

Les mesures provenant du dataset CSV utilisent :

```text
source = "csv"
dataset_id = identifiant du dataset
```

Cette représentation respecte les contraintes définies dans le schéma de la base.

### Dataset validé

Le dataset traité contient :

- 122 647 mesures ;
- 7 sites ;
- une période du 01/01/2023 au 31/12/2024 ;
- 0 doublon détecté dans les données sources.

Valeurs manquantes identifiées :

| Variable | Nombre de valeurs NULL |
|---|---:|
| `consumption_kwh` | 2 840 |
| `consumption_euros` | 2 487 |
| `temperature_celsius` | 3 416 |
| `humidity_percent` | 3 423 |
| `solar_irradiance_wm2` | 3 964 |

### Exécution historique en dry-run

Depuis le dossier :

```text
apps/backend/
```

exécuter :

```powershell
uv run python -m app.etl.historical_import `
  --csv ..\..\data\raw\all_sites_combined.csv `
  --metadata ..\..\data\raw\dataset_metadata.json `
  --source-timezone UTC `
  --dry-run
```

Aucune donnée n'est écrite dans la base pendant cette exécution.

### Chargement historique réel

Depuis `apps/backend/` :

```powershell
uv run python -m app.etl.historical_import `
  --csv ..\..\data\raw\all_sites_combined.csv `
  --metadata ..\..\data\raw\dataset_metadata.json `
  --source-timezone UTC
```

Le chargement est effectué progressivement par batches.

Exemple :

```text
Chargement : 1000/122647
Chargement : 2000/122647
...
Chargement : 122647/122647
```

### Résultats obtenus pour le dataset historique

Après le chargement initial, les contrôles en base ont confirmé :

```text
datasets = 1
sites    = 7
readings = 122647
source   = csv
```

Le premier import a créé :

```text
nouvelles lectures : 122647
```

### Idempotence du dataset historique

Le pipeline a été exécuté une deuxième fois avec exactement le même dataset afin de vérifier son idempotence.

Résultat :

```text
lectures avant     : 122647
lectures après     : 122647
nouvelles lectures : 0
```

Une nouvelle exécution du même import ne crée donc pas de mesures supplémentaires pour le dataset testé.

### Vérifications SQL du dataset historique

Depuis la racine du projet, vérifier le nombre d'enregistrements avec :

```powershell
docker compose exec db psql -U enervision -d enervision -c "SELECT COUNT(*) AS datasets FROM dataset; SELECT COUNT(*) AS sites FROM site; SELECT COUNT(*) AS readings FROM reading;"
```

Résultat attendu après l'import initial :

```text
datasets = 1
sites    = 7
readings = 122647
```

Vérifier la source des mesures avec :

```powershell
docker compose exec db psql -U enervision -d enervision -c "SELECT source, COUNT(*) FROM reading GROUP BY source ORDER BY source;"
```

Résultat attendu pour le dataset historique :

```text
csv | 122647
```

## Import depuis l'API Mock

### Fonctionnement

Le script d'import de l'API Mock se trouve dans :

```text
apps/backend/app/etl/mock_api_import.py
```

Le flux est le suivant :

```text
        API Mock
           |
     +-----+------+
     |            |
     v            v
   /sites      /readings
     |            |
     +-----+------+
           |
           v
 mock_api_import.py
           |
           v
 Transformation
 + qualité data
           |
           v
PostgreSQL / TimescaleDB
     |          |
     v          v
   site       reading
```

Le pipeline commence par récupérer les sites avec :

```text
GET /api/v1/sites
```

Il récupère ensuite les mesures de chaque site avec :

```text
GET /api/v1/readings
```

Les paramètres envoyés à `/api/v1/readings` sont :

```text
site_id
start_time
end_time
limit
```

Le paramètre `limit` doit être compris entre 1 et 1000.

### Configuration de l'API Mock

La connexion à l'API Mock est configurée avec les variables d'environnement suivantes :

```text
APP_MOCK_API_BASE_URL
APP_MOCK_API_USERNAME
APP_MOCK_API_PASSWORD
APP_MOCK_API_TIMEOUT_SECONDS
```

Les identifiants réels ne sont pas versionnés dans Git.

Les fichiers `.env.example` indiquent uniquement les variables nécessaires à l'exécution.

### Transformation des mesures API

Les mesures provenant de l'API Mock sont enregistrées dans `reading` avec :

```text
source = "api_history"
dataset_id = NULL
```

Les mesures provenant de l'API ne sont donc pas rattachées à un dataset historique.

Le timestamp reçu depuis l'API est converti en `datetime` avec timezone avant le chargement.

La réponse source est conservée dans :

```text
raw_data
```

afin de préserver la donnée reçue et faciliter la traçabilité.

### Qualité des données API

Les valeurs `NULL` fournies par l'API sont conservées telles quelles.

Une valeur manquante n'est pas transformée en zéro et la mesure n'est pas supprimée.

Le pipeline conserve également :

```text
data_quality
null_reasons
```

Les niveaux de qualité possibles sont :

```text
good
partial
degraded
critical
```

Ce sont les quatre seules valeurs que la contrainte `ck_reading_quality` accepte. Toute autre
valeur renvoyée par l'API est remplacée par `NULL` plutôt que de faire échouer le lot entier.

Aucune imputation n'est réalisée pendant l'ingestion :

```text
imputed_values = NULL
imputation_method = NULL
```

Cette stratégie permet de distinguer une véritable valeur nulle ou manquante d'une consommation égale à zéro et de conserver les informations liées aux défaillances de capteurs.

### Bornes physiques et frontière de confiance

La réponse de l'API Mock est traitée comme une entrée hostile : l'API n'a pas
d'authentification et expose un endpoint mutatif à quiconque. Voir API10 dans
`docs/architecture/owasp-traceabilite.md`.

Les plages acceptées sont déclarées dans `PHYSICAL_BOUNDS` :

| Grandeur | Plage acceptée |
|---|---|
| `consumption_kw` | 0 à 100 000 |
| `consumption_kwh` | 0 à 100 000 |
| `voltage_v` | 0 à 1 000 |
| `current_a` | 0 à 10 000 |
| `power_factor` | 0 à 1 |
| `temperature_celsius` | -90 à 60 |
| `humidity_percent` | 0 à 100 |
| `capacity_kw` | 0 à 100 000 |

Une valeur hors plage, d'un type inattendu, `NaN` ou infinie devient `NULL` :

```text
null_reasons += "out_of_physical_bounds:<colonne>"
data_quality = "degraded"
```

L'import ne s'interrompt pas pour autant : le mock émet des anomalies par construction, et
`raw_data` conserve la réponse d'origine.

La taille des réponses est plafonnée : au plus `MAX_SITES` sites, et au plus `--limit` mesures
par site. Au-delà, l'import échoue au lieu de charger.

Enfin, seuls les champs attendus sont recopiés vers la base. Une clé supplémentaire renvoyée par
l'API n'atteint jamais une colonne.

### Dry-run de l'API Mock

Le mode `--dry-run` permet de tester la connexion, la récupération des sites et la récupération des mesures sans écrire dans PostgreSQL.

Depuis `apps/backend/` :

```powershell
uv run python -m app.etl.mock_api_import `
  --start-time "2024-06-15T12:00:00" `
  --end-time "2024-06-15T13:00:00" `
  --limit 60 `
  --dry-run
```

### Chargement réel depuis l'API Mock

Depuis `apps/backend/` :

```powershell
uv run python -m app.etl.mock_api_import `
  --start-time "2024-06-15T12:00:00" `
  --end-time "2024-06-15T13:00:00" `
  --limit 60
```

### Résultat validé pour l'API Mock

Le scénario de validation utilisé couvre la période :

```text
15/06/2024 12:00 UTC
à
15/06/2024 13:00 UTC
```

avec une limite de 60 lectures par site.

Résultat obtenu :

```text
sites récupérés       : 7
lectures par site     : 60
lectures récupérées   : 420
source                : api_history
dataset_id            : NULL
```

Les contrôles effectués directement dans PostgreSQL/TimescaleDB ont confirmé :

- l'enregistrement des mesures dans `reading` ;
- la présence des 7 sites ;
- `source = "api_history"` ;
- `dataset_id = NULL` ;
- la conservation des valeurs `NULL` ;
- la conservation de `data_quality` ;
- la conservation de `null_reasons` ;
- la conservation de la donnée source dans `raw_data`.

### Idempotence de l'import API Mock

Le même import a été exécuté plusieurs fois afin de vérifier qu'une mesure déjà présente n'est pas créée une seconde fois.

L'idempotence repose sur la contrainte d'unicité de la table `reading` et sur la gestion des conflits lors de l'insertion.

Un test d'intégration automatisé vérifie également ce comportement.

## Tests et qualité

Les tests automatisés des pipelines ETL sont situés dans :

```text
apps/backend/tests/etl/
```

Les tests de l'import historique couvrent notamment :

- la validation du dataset ;
- les colonnes obligatoires ;
- la détection des doublons ;
- la cohérence des sites ;
- la normalisation des timestamps ;
- la gestion des valeurs manquantes ;
- la classification de la qualité des données ;
- la construction des mesures destinées à la BDD ;
- le respect des contraintes du modèle de données.

Les tests de l'import API Mock couvrent notamment :

- la récupération des sites ;
- l'appel à `/api/v1/readings` ;
- les paramètres `site_id`, `start_time`, `end_time` et `limit` ;
- la gestion des erreurs HTTP ;
- la validation du format de la réponse ;
- la transformation des mesures ;
- la conservation des valeurs `NULL` ;
- la conservation de `data_quality` et `null_reasons` ;
- `source = "api_history"` ;
- `dataset_id = NULL` ;
- la conservation de `raw_data` ;
- l'idempotence du chargement.

Exécuter les tests ETL :

```powershell
uv run pytest tests\etl -v
```

Exécuter les tests unitaires de l'import API Mock :

```powershell
uv run pytest tests\etl\test_mock_api_import.py -v
```

Exécuter le test d'intégration de l'import API Mock :

```powershell
uv run pytest tests\etl\test_mock_api_import.py -m integration -v
```

Contrôler la qualité du code :

```powershell
uv run ruff check app\etl tests\etl
```

Contrôler le typage :

```powershell
uv run mypy app
```

Exécuter la suite complète avec le seuil de couverture :

```powershell
uv run pytest --cov-fail-under=85
```

Lors de la validation de l'import API Mock :

```text
8 tests unitaires passés
1 test d'intégration passé
```

La suite backend complète a également été validée avec une couverture supérieure au seuil de 85 %.

## Suite du pipeline Data

Deux sources de données sont prises en charge par la logique ETL du backend :

```text
Dataset CSV/JSON
      |
      v
historical_import.py
      |
      +-----------------+
                        |
                        v
             PostgreSQL / TimescaleDB
                        ^
                        |
      +-----------------+
      |
mock_api_import.py
      ^
      |
   API Mock
```

La logique d'extraction, de validation, de transformation et de chargement est disponible pour
les deux sources de données du MVP.

Airflow tourne réellement dans `etl/airflow/` et orchestre désormais quatre DAGs :

```text
ml_train
ml_score
alertes
historical_import
```

Les DAGs `ml_train` et `ml_score` orchestrent le pipeline Machine Learning (issue #115).

Le DAG `alertes` orchestre la détection des alertes et la génération des recommandations
(issue #116).

Le DAG `historical_import` orchestre l'import du dataset historique CSV/JSON (issue #119).

### Orchestration de l'import historique

Le DAG historique est défini dans :

```text
etl/airflow/dags/historical_import.py
```

Il ne réimplémente aucune logique ETL. Il déclenche directement le module existant :

```text
app.etl.historical_import
```

Le flux d'exécution est le suivant :

```text
data/raw/
├── all_sites_combined.csv
└── dataset_metadata.json
          |
          v
Airflow
          |
          v
DAG historical_import
          |
          v
BashOperator
          |
          v
app.etl.historical_import
          |
          v
PostgreSQL / TimescaleDB
    |
    +--> dataset
    +--> site
    +--> reading
```

Les fichiers historiques locaux sont montés dans les conteneurs Airflow en lecture seule :

```text
./data/raw:/opt/data/raw:ro
```

Le DAG utilise les chemins suivants :

```text
/opt/data/raw/all_sites_combined.csv
/opt/data/raw/dataset_metadata.json
```

Le montage en lecture seule évite qu'un traitement Airflow puisse modifier les fichiers sources.

Le backend est déjà embarqué dans l'image Airflow dans son propre environnement Python :

```text
/opt/backend/.venv
```

Le DAG utilise un `BashOperator` avec le même principe que le DAG `alertes` :

```text
cd /opt/backend
env -u VIRTUAL_ENV
uv run --no-sync python -m app.etl.historical_import
```

Airflow reste ainsi responsable de l'orchestration tandis que le backend reste responsable de
l'extraction, de la validation, de la transformation et du chargement.

### Planification

Le dataset historique sert à initialiser l'environnement et n'est pas une source périodique.

Le DAG est donc configuré avec :

```text
schedule = None
catchup = False
max_active_runs = 1
```

Le déclenchement est manuel depuis l'interface Airflow ou avec la CLI.

`max_active_runs = 1` empêche deux imports historiques de s'exécuter simultanément.

La tâche `import_historical` définit également :

```text
retries = 1
retry_delay = 2 minutes
execution_timeout = 30 minutes
```

Le retry permet de reprendre le traitement après une erreur transitoire, notamment une
indisponibilité temporaire de PostgreSQL.

Le pipeline historique étant idempotent, une nouvelle exécution ne doit pas dupliquer les mesures
déjà présentes.

### Déclenchement et suivi

Le DAG peut être déclenché avec :

```powershell
docker compose exec airflow-scheduler airflow dags trigger historical_import
```

Les exécutions peuvent être consultées avec :

```powershell
docker compose exec airflow-scheduler airflow dags list-runs -d historical_import
```

### Validation de l'orchestration

L'orchestration a été validée localement avec Docker Compose et le `LocalExecutor` Airflow.

Le scheduler détecte les quatre DAGs :

```text
alertes
historical_import
ml_score
ml_train
```

Deux exécutions manuelles successives du DAG `historical_import` ont été réalisées.

Les deux exécutions se sont terminées avec :

```text
state = success
```

Les exécutions ont été traitées séquentiellement.

Après les deux exécutions, PostgreSQL/TimescaleDB contenait toujours :

```text
122647
```

lectures historiques avec :

```text
source = "csv"
```

Le nombre de lectures n'a donc pas doublé après la seconde exécution.

Cette validation confirme que l'orchestration Airflow réutilise correctement
`app.etl.historical_import` et conserve l'idempotence du pipeline historique.

### Suite

L'import de l'API Mock est déjà disponible côté backend avec :

```text
app.etl.mock_api_import
```

Son orchestration Airflow ainsi que la réconciliation globale entre les sources historique et
API Mock restent à compléter dans l'issue #15.

Airflow ne remplace pas les pipelines Python existants : il orchestre leur exécution, leur
planification, les reprises sur erreur et leur suivi.