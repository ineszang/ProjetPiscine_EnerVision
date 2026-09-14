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

## Commandes

Depuis la racine du monorepo, via le `Makefile` : `make install`, `make dev`, `make lint`,
`make format`, `make typecheck`, `make test`, `make check`, `make docker-build`.

Directement depuis ce dossier :

```bash
uv run uvicorn app.main:create_app --factory --reload --port 8000
uv run ruff check .          # lint
uv run ruff format .         # format
uv run mypy app              # typage strict
uv run pytest                # tests + couverture
```

L'application est exposee par une factory (`create_app`) et non par un objet module :
aucune configuration n'est lue a l'import, ce qui rend les tests et les migrations
independants de l'environnement.

## Structure

```
app/
├── api/
│   ├── deps.py          Dependances FastAPI partagees (session, settings)
│   └── v1/
│       ├── router.py    Agregation des routes de la version 1
│       └── endpoints/   Un module par ressource exposee
├── core/
│   ├── config.py        Settings Pydantic, source unique de configuration
│   └── logging.py       Journalisation console en local, JSON en production
├── db/
│   ├── base.py          Base declarative SQLAlchemy
│   └── session.py       Engine et sessions asynchrones
├── models/              Modeles SQLAlchemy
├── schemas/             Modeles Pydantic d'entree et de sortie
├── repositories/        Acces aux donnees, une classe par agregat
├── services/            Regles metier, orchestrent les repositories
└── main.py              Factory applicative
tests/                   Miroir de app/
alembic/                 Migrations du schema applicatif
```

Le sens de dependance est unique : `endpoints` vers `services` vers `repositories` vers
`models`. Un endpoint ne touche jamais une session directement.

## Routes

| Route                  | Role                                            |
|------------------------|-------------------------------------------------|
| `/api/v1/health/live`  | Sonde de vivacite, aucune dependance externe    |
| `/api/v1/health/ready` | Sonde de disponibilite, verifie la base         |
| `/metrics`             | Metriques au format Prometheus                  |
| `/docs`, `/openapi.json` | Documentation, desactivee quand `APP_ENV=prod` |

## Migrations

```bash
uv run alembic revision --autogenerate -m "libelle"
uv run alembic upgrade head
```

L'URL de connexion vient de `DATABASE_URL`, pas de `alembic.ini`.

## Image Docker

Build multi-stage, dependances resolues par uv depuis `uv.lock`, execution sous un
utilisateur non root, sonde de sante integree.

```bash
docker build -t enervision-backend:local .
docker run --rm -p 8000:8000 --env-file .env enervision-backend:local
```
