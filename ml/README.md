# ML EnerVision

Pipeline d'entrainement du modele de prevision de consommation energetique. Contexte complet :
[ADR 0005](../docs/adr/0005-modele-prediction-lightgbm.md) (choix du modele) et
[ML-START.md](../ML-START.md) (mecanisme d'acces aux donnees).

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

Un serveur MLflow (PostgreSQL pour les metadonnees, volume pour les artefacts) se lance avec
Docker. Prerequis : Docker Desktop demarre.

```
cd ml
docker compose -f docker-compose.mlflow.yml up -d --build
```

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

Limites : les identifiants PostgreSQL (`mlflow` / `mlflow`) du compose ne conviennent qu'au
developpement local. Un deploiement partage demandera des secrets, de l'authentification et un
stockage d'artefacts dedie (S3/MinIO). Le port 5000 doit etre libre : arreter `mlflow ui` avant,
ou changer le mapping (`"5001:5000"`) dans le compose.

## Commandes

```bash
uv run ruff check .                       # lint
uv run ruff format .                      # format
uv run mypy enervision_ml tests           # typage strict
uv run pytest                             # tests
```

Depuis la racine du monorepo, via le `Makefile` : `make install-ml`, `make ml-lint`,
`make ml-typecheck`, `make ml-test`, `make ml-check`, `make ml-train` (`CSV=chemin` optionnel).

## Ou ecrire les tests

Aucun test ne touche PostgreSQL ni un serveur MLflow distant : `enervision_ml.data.load_from_csv`
et le chargement CSV de test suffisent a exercer `build_features` sur des donnees reelles ou
synthetiques, et `enervision_ml.train.train()` accepte un `tracking_uri` SQLite isole (`tmp_path`
pytest) pour un test de bout en bout sans effet de bord. `enervision_ml.data.load_from_database`
n'est pas encore couvert : il n'existe aucune base PostgreSQL a interroger en CI ni dans cet
environnement de developpement pour le moment.

## Piege a connaitre

`enervision_ml.features.build_features` est **le seul endroit** qui doit construire les features
du modele, a l'entrainement comme au futur scoring (service #37, pas encore construit). Si les
deux divergent meme legerement (une fenetre de moyenne glissante calculee differemment, par
exemple), le modele recoit en production des features qui ne ressemblent plus a ce qu'il a
appris, et ses predictions deviennent silencieusement mauvaises sans qu'aucune erreur ne se
declenche. Ne jamais reecrire cette logique ailleurs : importer `enervision_ml.features`.
