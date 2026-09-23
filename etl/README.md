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

Deux sources de données sont maintenant prises en charge :

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

La logique d'extraction, de transformation et de chargement est donc disponible pour les deux sources de données du MVP.

Airflow tourne désormais réellement (`etl/airflow/`, `make airflow-up`) et orchestre cinq DAGs :
le pipeline ML (`ml_train` et `ml_score`, issue #115), la détection d'alertes et la génération
des recommandations (`alertes`, issue #116), l'import historique (`historical_import`,
issue #119) et l'import périodique de l'API Mock (`mock_api_import`, issue #15).

Le DAG `mock_api_import` s'exécute chaque heure, à la minute `:45`, sur un intervalle explicite
d'une heure. L'API Mock génère autant de points que la limite demandée, répartis sur
l'intervalle : `app.etl.mock_api_import.limit_for_window()` dérive donc `limit` de la fenêtre
reçue (une lecture par site pour cette fenêtre d'1h) plutôt que de dépendre d'une valeur fixée à
la main côté DAG, et refuse une fenêtre qui ne couvre pas un nombre entier d'heures. La fenêtre
`[:45, :45)` place cette lecture à :45, pas à :00 (l'API place son premier point au début de la
fenêtre demandée), un décalage constant sans effet sur les lags positionnels ML ni sur les
jointures en aval. Les deux pipelines normalisent leurs données vers les tables communes `site` et
`reading`, tout en conservant leur source (`csv` ou `api_history`). La réconciliation entre les
deux sources (issue #15) est close : voir `docs/architecture/40-data.md`.

Le DAG `mock_api_import` exécute `app.etl.mock_api_import` toutes les heures. Chaque exécution
traite l'intervalle Airflow précédent. Les deux pipelines normalisent leurs données vers les
tables communes `site` et `reading`, tout en conservant leur source (`csv` ou `api_history`).

Airflow permet de planifier les traitements, gérer leur ordre d'exécution, suivre leur état et remonter les erreurs. Il ne remplace pas la logique ETL Python existante : les scripts actuels restent responsables de l'extraction, de la validation, de la transformation et du chargement. `etl/airflow/dags/ml_train.py`, `ml_score.py`, `alertes.py`, `historical_import.py` et
`mock_api_import.py` montrent le patron retenu (des `BashOperator` qui invoquent le script tel quel, dans l'environnement `uv` que l'image embarque pour lui).

Le pipeline Data servira ensuite à préparer les données nécessaires au modèle de Machine Learning.
