# ML EnerVision

Pipeline d'entrainement du modele de prevision de consommation energetique. Contexte complet :
[ADR 0005](../docs/adr/0005-modele-prediction-lightgbm.md) (choix du modele) et
[ML-START.md](../docs/ML-START.md) (mecanisme d'acces aux donnees).

| Element      | Choix                                        |
|--------------|-----------------------------------------------|
| Python       | 3.14                                          |
| Gestionnaire | uv (`uv.lock` fait foi)                       |
| Modele       | LightGBM (regression, un seul modele global)  |
| Suivi        | MLflow (parametres, metriques, artefact)      |
| Lint/format  | ruff                                          |
| Typage       | mypy en mode strict                           |
| Tests        | pytest, donnees synthetiques uniquement       |

Projet Python independant de `apps/backend` : le service FastAPI n'a aucune raison d'embarquer
LightGBM/MLflow en dependance de production juste pour un script d'entrainement lance a la main.

## Installation

```bash
uv sync --all-groups
```

## Donnees

Deux sources, qui produisent le meme schema en sortie de `enervision_ml.data` (voir le module
pour le detail) :

- **CSV** (`--csv`), chemin de demarrage : lit directement `ml/data/all_sites_combined.csv`, le
  jeu de donnees fourni pour le jalon J3. Ce dossier est ignore par git (gros fichier, local a
  chaque poste) : recuperer le CSV et `dataset_metadata.json` aupres de l'equipe et les placer
  dans `ml/data/` avant d'entrainer sur cette source.
- **PostgreSQL** (par defaut, sans `--csv`) : connexion directe a `reading` + `site` via
  `ML_DATABASE_URL`, le chemin cible decrit dans `ML-START.md`. Le role PostgreSQL dedie
  `enervision_ml` (lecture seule) n'est pas encore provisionne (dette assumee, cf. ADR 0003 et
  ADR 0005) ; en attendant, pointer `ML_DATABASE_URL` vers la meme base que le backend suffit en
  developpement.

## Entrainement

```bash
uv run python -m enervision_ml.train --csv data/all_sites_combined.csv
# ou, une fois la base peuplee et ML_DATABASE_URL positionnee :
uv run python -m enervision_ml.train
```

Ecrit le modele entraine dans `models/lightgbm-consumption.txt` (`Booster.save_model()`, dossier
ignore par git) et journalise la run dans MLflow : parametres, MAE/RMSE/MAPE du modele **et** de
la baseline de persistance saisonniere (consommation de la meme heure, une semaine avant), et
l'artefact modele. Sans `MLFLOW_TRACKING_URI`, MLflow ecrit dans un magasin SQLite local
(`./mlflow.db`, ignore par git) : `uv run mlflow ui` pour le consulter.

`--test-fraction` (0.15 par defaut) fixe la part la plus recente de l'historique reservee a la
validation. La coupure est **chronologique**, jamais un tirage aleatoire de lignes : un tirage
aleatoire laisserait des lignes de validation "voir" des lignes d'entrainement via leurs
lags/moyennes glissantes, une fuite qui masquerait un surapprentissage.

## Serveur MLflow (conteneur)

Premiere utilisation : copier `.env.example` en `.env` et y choisir un mot de passe PostgreSQL
(lettres et chiffres uniquement). Le fichier `.env` est ignore par git.

```bash
cp .env.example .env
```

Un serveur MLflow (PostgreSQL pour les metadonnees, volume pour les artefacts) se lance avec
Docker. Prerequis : Docker Desktop demarre.

```bash
make mlflow-up
```

La cible vérifie que `MLFLOW_DB_PASSWORD` (définie dans `ml/.env`) ne contient que des lettres et
des chiffres avant de démarrer le serveur : ce mot de passe est interpolé directement dans l'URI
PostgreSQL (`postgresql://mlflow:${MLFLOW_DB_PASSWORD}@...`), un caractère spécial la rendrait
invalide sans message d'erreur clair.

Interface : http://localhost:5000. Entrainer vers ce serveur :

```
uv run python -m enervision_ml.train --csv data/all_sites_combined.csv --mlflow-tracking-uri http://localhost:5000
```

Arreter : `docker compose -f docker-compose.mlflow.yml down` (ajouter `-v` pour effacer aussi les
runs et les modeles).

Pour voir les runs dans l'interface (MLflow 3.x) :

- Passer le selecteur en haut a gauche sur **Model training**. Le mode **GenAI** affiche des
  traces LLM et reste vide pour un entrainement LightGBM.
- **Runs** liste les entrainements, **Models** les artefacts de modele de chaque run (tous nommes
  `model`), et **Model registry** les versions numerotees de `consumption-forecast-lightgbm`.

Limites : l'identifiant PostgreSQL du compose est fixe a `mlflow`, le mot de passe vient de la
variable obligatoire `MLFLOW_DB_PASSWORD` (aucune valeur par defaut, le compose refuse de
demarrer sans elle) -- ce mot de passe est choisi lors de la copie de `.env.example`, il ne
convient donc qu'au developpement local tel quel. Un deploiement partage demandera des secrets,
de l'authentification et un stockage d'artefacts dedie (S3/MinIO). Le port 5000 doit etre libre : arreter `mlflow ui` avant,
ou changer le mapping (`"5001:5000"`) dans le compose.

## Scoring

```bash
uv run python -m enervision_ml.score --csv data/all_sites_combined.csv
# ou, une fois la base peuplee et ML_DATABASE_URL positionnee :
uv run python -m enervision_ml.score
```

Calcule, pour chaque site (ou un seul avec `--site-id`), la consommation prevue de l'heure suivant
sa derniere lecture connue, et ecrit une ligne dans `prediction`. Etapes, cf. `ML-START.md`
section 2 :

1. Lit une fenetre recente de `reading`+`site` (21 jours par defaut, une marge au-dessus des 168h
   necessaires au lag hebdomadaire) plutot que tout l'historique -- le meme piege que celui deja
   corrige sur `GET /readings` (fenetre non plafonnee sur une hypertable).
2. Ajoute une ligne "future" par site (l'heure suivante) et calcule ses features avec
   `enervision_ml.features.build_features`, **exactement** la meme fonction qu'a l'entrainement.
3. Si le lag de 168h est absent (moins d'une semaine d'historique pour ce site) : ecrit
   `status="insufficient_data"` directement, sans jamais appeler LightGBM.
4. Sinon : appelle `booster.predict(...)` et ecrit `status="available"` avec la valeur predite.

`--model` pointe vers le fichier entraine (`models/lightgbm-consumption.txt` par defaut).
`model_reference` en base est le hache SHA-256 (tronque) du fichier modele, pas son nom de
fichier : `train.py` reecrit toujours le meme chemin a chaque entrainement, donc le nom seul ne
distinguerait pas deux versions du modele.

**Le scoring ne lit pas le Model Registry.** Le fichier charge par `--model` est local
(`models/lightgbm-consumption.txt`), independant des versions enregistrees dans le
**Model registry** MLflow (`consumption-forecast-lightgbm`). `train.py` enregistre bien une
version a chaque entrainement (tracabilite), mais aucun alias (`champion` par exemple) n'est
pose, et `enervision_ml.score` ne les lit pas. Le registre sert aujourd'hui a la tracabilite des
entrainements, pas au deploiement du modele utilise en scoring.

En mode `--csv`, rien n'est ecrit en base : c'est un instantane historique fige (l'heure "future"
calculee a partir de la fin du CSV n'existe dans aucune base reelle), utile pour valider le
pipeline sans base joignable.

**Limite assumee** : la feature `is_working_hours` de la ligne future est recopiee depuis la
derniere lecture reelle, pas recalculee -- il n'existe aucune regle horaire ouvrable dans ce
depot (elle vit dans le generateur du jeu de donnees d'origine). L'approximation n'est fausse
qu'aux heures de bascule ouverture/fermeture, sur une seule feature parmi une dizaine, pour une
prevision a un seul pas.

`prediction` n'a pas de contrainte d'unicite sur `(site_id, target_at)` : chaque run de scoring
insere une nouvelle ligne plutot que d'ecraser la precedente, pour garder une trace de chaque
prevision (utile plus tard pour comparer prevision et realise, surveillance de derive #44/#45).

## Commandes

```bash
uv run ruff check .                       # lint
uv run ruff format .                      # format
uv run mypy enervision_ml tests           # typage strict
uv run pytest                             # tests + couverture (ml/coverage.xml avec --cov-report=xml, lu par Sonar)
```

Depuis la racine du monorepo, via le `Makefile` : `make install-ml`, `make ml-lint`,
`make ml-typecheck`, `make ml-test`, `make ml-check`, `make ml-train` (`CSV=chemin` optionnel).

## Ou ecrire les tests

Deux regimes, separes par le marqueur `integration` que `pytest` ecarte par defaut.

**Sans base** : `enervision_ml.data.load_from_csv` et le chargement CSV de test suffisent a
exercer `build_features` sur des donnees reelles ou synthetiques, et `enervision_ml.train.train()`
accepte un `tracking_uri` SQLite isole (`tmp_path` pytest) pour un test de bout en bout sans effet
de bord.

**Avec base**, sous `integration` : `test_data_integration.py` confronte les neuf colonnes du
contrat au schema Alembic reel, et `test_score_integration.py` verifie les contraintes de
`prediction` depuis le code qui ecrit. Les fixtures sont dans `tests/conftest.py`, qui refuse de
demarrer si `ML_DATABASE_URL` ne vise pas `enervision_test`.

    make db-up migrate-test ml-test-integration

Regle a tenir : **toute requete SQL nouvelle porte un test `integration`**. Le schema vit dans
`apps/backend/alembic`, pas ici : sans ce garde-fou, une migration qui renomme une colonne casse
le pipeline en production sans qu'aucun test ne rougisse.

## Piege a connaitre

`enervision_ml.features.build_features` est **le seul endroit** qui doit construire les features
du modele, a l'entrainement comme au scoring (`enervision_ml.score`). Si les deux divergent meme
legerement (une fenetre de moyenne glissante calculee differemment, par exemple), le modele
recoit en production des features qui ne ressemblent plus a ce qu'il a appris, et ses predictions
deviennent silencieusement mauvaises sans qu'aucune erreur ne se declenche. Ne jamais reecrire
cette logique ailleurs : importer `enervision_ml.features`.

## Et cote API ?

`GET /api/v1/predictions` (backend, `apps/backend`) lit ce que `enervision_ml.score` a ecrit dans
`prediction` -- la derniere prevision par site, jamais un recalcul a la volee. FastAPI ne fait
jamais tourner LightGBM lui-meme, cf. `ML-START.md` section 3.
