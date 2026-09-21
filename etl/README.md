# Pipeline ETL — EnerVision

## Objectif

Le pipeline ETL EnerVision permet d'intégrer les données énergétiques historiques dans PostgreSQL/TimescaleDB.

Cette première étape du pipeline Data permet de charger le dataset fourni dans le cadre du projet, contenant les mesures énergétiques de 7 sites sur la période du 1er janvier 2023 au 31 décembre 2024.

Le pipeline assure :

- l'extraction des données sources ;
- la validation de leur structure et de leur cohérence ;
- la normalisation des données nécessaires au stockage ;
- le suivi de la qualité des données ;
- la traçabilité du dataset importé ;
- le chargement des données dans PostgreSQL/TimescaleDB ;
- l'idempotence du chargement afin d'éviter la création de doublons.

## Données sources

Le dataset est fourni par le formateur dans le cadre du projet EnerVision.

Il contient les deux fichiers suivants :

```text
all_sites_combined.csv
dataset_metadata.json
```

Ces fichiers sont nécessaires une seule fois pour initialiser les données historiques de l'environnement.

Ils ne sont pas versionnés dans Git. Chaque membre de l'équipe récupère manuellement une fois les fichiers fournis par le formateur et les place dans :

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

## Technologies utilisées

| Technologie | Utilisation |
|---|---|
| Python | Développement du pipeline ETL |
| Pandas | Lecture, validation et transformation des données |
| JSON | Lecture des métadonnées du dataset |
| hashlib / SHA-256 | Identification, intégrité et traçabilité du dataset |
| SQLAlchemy Async | Connexion et chargement asynchrone en base |
| PostgreSQL | Stockage relationnel |
| TimescaleDB | Stockage des séries temporelles énergétiques |
| Docker Compose | Exécution de l'environnement local |
| Alembic | Gestion des migrations du schéma |
| uv | Gestion et exécution de l'environnement Python |
| Ruff | Contrôle de la qualité du code |
| Pytest | Tests automatisés |

## Fonctionnement du pipeline

Le script principal d'import se trouve dans :

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

### 1. Extraction

Le pipeline charge :

- `all_sites_combined.csv` avec Pandas ;
- `dataset_metadata.json` avec le module JSON de Python.

### 2. Validation

Avant toute écriture en base, le pipeline contrôle notamment :

- la présence des colonnes obligatoires ;
- le nombre de lignes ;
- la cohérence des identifiants des sites ;
- la cohérence des informations associées aux sites ;
- les doublons sur le couple `(site_id, timestamp)` ;
- les timestamps ;
- les valeurs manquantes.

Une incohérence détectée pendant cette étape interrompt l'import avant le chargement.

### 3. Dry-run

Un mode `--dry-run` permet d'exécuter les contrôles sans écrire de données dans PostgreSQL.

Il permet notamment de vérifier :

- le nombre de lignes ;
- le nombre de sites ;
- la période couverte ;
- les doublons ;
- les valeurs NULL ;
- l'empreinte SHA-256.

### 4. Traçabilité

Une empreinte SHA-256 est calculée à partir du fichier CSV afin d'identifier le dataset utilisé.

Empreinte SHA-256 du dataset validé :

```text
6E3777A97A5660B11855750B9028F70BE72138A11F26795F3A35D9CE74CE0C8D
```

Cette empreinte participe à la traçabilité du dataset chargé.

### 5. Transformation

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

### 6. Chargement

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

## Dataset validé

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

## Exécution en dry-run

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

## Chargement réel

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

## Résultats obtenus

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

## Idempotence

Le pipeline a été exécuté une deuxième fois avec exactement le même dataset afin de vérifier son idempotence.

Résultat :

```text
lectures avant     : 122647
lectures après     : 122647
nouvelles lectures : 0
```

Une nouvelle exécution du même import ne crée donc pas de mesures supplémentaires pour le dataset testé.

## Vérifications SQL

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

Résultat attendu :

```text
csv | 122647
```

## Tests et qualité

Les tests automatisés du pipeline sont situés dans :

```text
apps/backend/tests/etl/
```

Ils couvrent notamment :

- la validation du dataset ;
- les colonnes obligatoires ;
- la détection des doublons ;
- la cohérence des sites ;
- la normalisation des timestamps ;
- la gestion des valeurs manquantes ;
- la classification de la qualité des données ;
- la construction des mesures destinées à la BDD ;
- le respect des contraintes du modèle de données.

Exécuter les tests ETL :

```powershell
uv run pytest tests\etl -v
```

Contrôler la qualité du code :

```powershell
uv run ruff check app\etl tests\etl
```

## Suite du pipeline Data

L'import historique constitue la première brique du pipeline Data EnerVision.

Airflow tourne désormais réellement (`etl/airflow/`, `make airflow-up`), mais orchestre pour l'instant le pipeline ML (`ml_train`/`ml_score`, issue #115), pas encore ce pipeline ETL : orchestrer `historical_import.py` (normalisation et chargement micro-batch, issues #15/#16) reste à faire.

Le principe reste le même que documenté à l'origine : Airflow orchestre les traitements existants sans remplacer leur logique métier, cf. `etl/airflow/dags/ml_train.py`/`ml_score.py` pour un exemple concret de ce patron (des `BashOperator` qui invoquent le script tel quel).