# EnerVision

Monorepo de la plateforme EnerVision : collecte, stockage, analyse et restitution de
series temporelles energetiques, deployee sur une machine on-premise.

## Jalons

| Jalon | Intitulé |
|-------|----------------------------------------------------------|
| J1    | Valider la préparation de l'environnement et du repo     |
| J2    | Valider le périmètre retenu et les choix technologiques  |
| J3    | Valider l'architecture et la gestion de la sécurité      |
| J4    | Valider la robustesse et assurer les livrables           |

Ce que la documentation apporte à chacun : [docs/architecture/00-vue-ensemble.md](docs/architecture/00-vue-ensemble.md).

## Stack cible

| Domaine    | Technologie                         | Emplacement         | Etat          |
|------------|-------------------------------------|---------------------|---------------|
| Backend    | FastAPI, Python 3.14                | `apps/backend`      | Initialise    |
| Frontend   | Angular 22, Node 24 LTS             | `apps/frontend`     | Squelette     |
| Base       | PostgreSQL 17 + TimescaleDB         | `db`                | Initialise    |
| ETL        | Apache Airflow                      | `etl/airflow`       | A initialiser |
| Infra      | Terraform (k3s single-node)         | `infra/terraform`   | Initialise    |
| CI/CD      | GitHub Actions                      | `.github/workflows` | Backend en place |
| Monitoring | Prometheus, Grafana, Alertmanager   | `monitoring`        | A initialiser |

Le backend, la base et l'infrastructure (Terraform/k3s) sont initialises a ce stade. Le frontend
porte le squelette Angular, sans code metier : aucune route, aucun appel d'API. Les autres dossiers
portent l'arborescence et un README de cadrage, leur contenu fait l'objet d'un ticket dedie.

L'etat detaille de chaque brique et les vues d'architecture sont dans
[docs/architecture](docs/architecture/README.md).

## Arborescence

```
.
├── apps/
│   ├── backend/        API FastAPI
│   └── frontend/       Application Angular
├── db/
│   ├── init/           Bootstrap PostgreSQL + TimescaleDB
│   ├── migrations/     Migrations SQL versionnees
│   └── seeds/          Jeux de donnees de reference
├── etl/airflow/
│   ├── dags/           DAGs d'ingestion et d'agregation
│   ├── plugins/        Operateurs et hooks maison
│   ├── include/        Requetes SQL et ressources des DAGs
│   └── tests/          Tests d'integrite des DAGs
├── infra/terraform/
│   ├── modules/        Modules reutilisables
│   └── environments/   Racines Terraform, une par environnement
├── monitoring/
│   ├── prometheus/     Collecte et regles d'alerte
│   ├── grafana/        Provisioning et dashboards
│   └── alertmanager/   Routage des alertes
├── docs/               ADR et vues d'architecture
└── scripts/            Outillage local
```

## Demarrage

Prerequis : uv, Docker. Le poste doit disposer de Python 3.14, que `uv` installe seul.

```bash
cp .env.example .env                               # variables de docker-compose
cp apps/backend/.env.example apps/backend/.env     # variables du backend hors conteneur

make db-up     # PostgreSQL + TimescaleDB, publie sur le port 5433
make install   # dependances du backend
make migrate   # applique les migrations Alembic
make dev       # API sur http://localhost:8000, docs sur /docs
make check     # lint + typage + tests
```

`make help` liste les cibles disponibles.

Deux fichiers d'environnement, deux usages : `.env` a la racine alimente `docker-compose.yml`,
`apps/backend/.env` alimente le backend lance sur le poste. Le port 5433 est publie plutot que
5432, souvent deja pris par une autre base.

La boucle de developpement est `make db-up` puis `make dev` : seule la base tourne en
conteneur. Le service `backend` du `docker-compose.yml` sert la stack complete et la recette,
et n'embarque pas le source, donc toute modification y demande un
`docker compose up -d --build backend`.

Verifier que la base repond et que l'extension est chargee :

```bash
curl -s localhost:8000/api/v1/health/ready
```

## Conventions

- Branches : `feat/`, `fix/`, `chore/`, `docs/`, `test/` suivi d'un libelle court.
- Commits : Conventional Commits, portee = dossier de premier niveau concerne.
- Toute decision structurante donne lieu a un ADR dans `docs/adr`.
- Toute PR qui change un composant met a jour sa vue dans `docs/architecture`, dans la meme PR.
