# Backend EnerVision

API FastAPI exposant les series temporelles energetiques.

| Element     | Choix                                      |
|-------------|--------------------------------------------|
| Python      | 3.14                                       |
| Gestionnaire| uv (`uv.lock` fait foi)                    |
| Framework   | FastAPI + Uvicorn                          |
| Persistance | SQLAlchemy 2 async + asyncpg + Alembic     |
| Lint/format | ruff                                       |
| Typage      | mypy en mode strict                        |
| Tests       | pytest + pytest-asyncio + httpx            |

## Installation

```bash
cp .env.example .env
uv sync --all-groups
```

`APP_SECRET_KEY` et `DATABASE_URL` n'ont pas de valeur par defaut : l'application refuse
de demarrer sans elles.

`DATABASE_URL` pointe sur `localhost:5433`, le port publie par le service `db` du
`docker-compose.yml` racine. Demarrer la base depuis la racine avec `make db-up`.

## Commandes

Depuis la racine du monorepo, via le `Makefile` : `make install`, `make dev`, `make lint`,
`make format`, `make typecheck`, `make test`, `make check`, `make openapi`, `make docker-build`.

Directement depuis ce dossier :

```bash
uv run uvicorn app.main:create_app --factory --reload --port 8000
uv run ruff check .          # lint
uv run ruff format .         # format
uv run mypy app              # typage strict
uv run pytest                # tests + couverture
uv run pytest -m integration # tests exigeant une base joignable
uv run python -m app.cli export-openapi   # régénère openapi.json
```

`openapi.json` est versionné : `tests/api/test_openapi.py` échoue si le fichier ne correspond
plus aux routes déclarées. Toute PR qui change une route le régénère dans le même commit.

Les conventions de tests, les gabarits et le detail des marqueurs sont dans
[`TESTING.md`](TESTING.md).

`pytest` ecarte par defaut les tests marques `integration`, pour que `make check` reste
jouable sans Docker. Ces tests visent la base `enervision_test`, creee par
`db/init/110-test-database.sql` au premier demarrage du conteneur.

L'application est exposee par une factory (`create_app`) et non par un objet module :
aucune configuration n'est lue a l'import, ce qui rend les tests et les migrations
independants de l'environnement.

## Structure

```
app/
├── api/
│   ├── deps.py          Dépendances partagées : session, settings, principal, gardes de rôle
│   ├── errors.py        Gestionnaires 422 et 500
│   ├── middleware.py    En-têtes de sécurité
│   ├── security.py      Garde du point /metrics
│   └── v1/
│       ├── router.py    Agrégation des routes de la version 1
│       └── endpoints/   Un module par ressource exposée
├── core/
│   ├── config.py        Settings Pydantic, source unique de configuration
│   ├── cookies.py       Attributs du cookie de rafraîchissement
│   ├── hashing.py       Argon2id, poussé dans un fil sous limiteur
│   ├── logging.py       Journalisation console en local, JSON en production
│   ├── principal.py     L'identité que voit le code métier
│   ├── roles.py         Rôles ordonnés
│   └── security.py      Encodage et décodage des jetons d'accès
├── db/
│   ├── base.py          Base declarative SQLAlchemy
│   └── session.py       Engine et sessions asynchrones
├── models/              Modeles SQLAlchemy
├── schemas/             Modeles Pydantic d'entree et de sortie
├── repositories/        Acces aux donnees, une classe par agregat
├── services/            Regles metier, orchestrent les repositories
├── cli.py               Commandes hors HTTP, dont l'amorcage du premier admin
└── main.py              Factory applicative
tests/                   Miroir de app/
alembic/                 Migrations du schema applicatif
```

Le sens de dependance est unique : `endpoints` vers `services` vers `repositories` vers
`models`. Un endpoint ne touche jamais une session directement.

## Routes

| Route | Rôle | Accès |
|---|---|---|
| `/api/v1/health/live` | Sonde de vivacité, aucune dépendance externe | public |
| `/api/v1/health/ready` | Sonde de disponibilité, vérifie la base et TimescaleDB | public |
| `/api/v1/auth/login` | Ouvre une session | public |
| `/api/v1/auth/refresh` | Fait tourner la session | cookie |
| `/api/v1/auth/logout` | Ferme la session courante | cookie, idempotente |
| `/api/v1/auth/logout-all` | Ferme toutes les sessions du compte | jeton |
| `/api/v1/auth/password` | Change son propre mot de passe | jeton |
| `/api/v1/auth/me` | Décrit le compte connecté | jeton |
| `/api/v1/users` | Liste et crée des comptes | `admin` |
| `/api/v1/users/{id}` | Change le rôle ou l'activation | `admin` |
| `/api/v1/users/{id}/password-reset` | Réinitialise et ferme les sessions | `admin` |
| `/api/v1/sites` | Liste les sites | `lecteur` |
| `/api/v1/sites/{site_id}` | Décrit un site | `lecteur` |
| `/metrics` | Métriques au format Prometheus | jeton si `APP_METRICS_TOKEN` |
| `/docs`, `/openapi.json` | Documentation, fermée en `staging` et `prod` | public sinon |

Le contrat détaillé pour le frontend est dans
[`docs/architecture/31-contrat-authentification.md`](../../docs/architecture/31-contrat-authentification.md).

## Premier administrateur

Aucun compte n'existe après les migrations. Il s'en crée un en ligne de commande :

```bash
make bootstrap-admin EMAIL=prenom.nom@enervision.fr   # mot de passe saisi au clavier
# ou, depuis apps/backend :
uv run python -m app.cli create-admin --email prenom.nom@enervision.fr --generate
```

Le compte est créé avec `must_change_password`, donc la première connexion ne donne accès qu'à
`/auth/me` et `/auth/password` jusqu'au changement. Le mot de passe ne transite jamais par
`argv`, visible de tout `ps`, et aucune révision Alembic n'insère de compte : son empreinte
resterait dans Git pour toujours.

## Migrations

```bash
uv run alembic revision --autogenerate -m "libelle"
uv run alembic upgrade head
```

L'URL de connexion vient de `DATABASE_URL`, pas de `alembic.ini`.

La premiere revision ne cree aucune table : elle refuse de s'appliquer si l'extension
TimescaleDB manque, ce qui arrive quand `db/init` n'a pas ete joue. Le DDL propre a
TimescaleDB qui ne depend pas du schema applicatif vit dans `db/`, pas ici.

## Image Docker

Build multi-stage, dependances resolues par uv depuis `uv.lock`, execution sous un
utilisateur non root, sonde de sante integree.

```bash
docker build -t enervision-backend:local .
docker run --rm -p 8000:8000 --env-file .env enervision-backend:local
```
