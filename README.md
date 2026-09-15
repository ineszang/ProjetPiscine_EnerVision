# EnerVision

Monorepo de la plateforme EnerVision : collecte, stockage, analyse et restitution de
series temporelles energetiques, deployee sur une machine on-premise.

## Stack cible

| Domaine    | Technologie                         | Emplacement         | Etat          |
|------------|-------------------------------------|---------------------|---------------|
| Backend    | FastAPI, Python 3.14                | `apps/backend`      | Initialise    |
| Frontend   | Angular, Node 24 LTS                | `apps/frontend`     | A initialiser |
| Base       | PostgreSQL 17 + TimescaleDB         | `db`                | Initialise    |
| ETL        | Apache Airflow                      | `etl/airflow`       | A initialiser |
| Infra      | Terraform                           | `infra/terraform`   | A initialiser |
| CI/CD      | GitHub Actions                      | `.github/workflows` | A initialiser |
| Monitoring | Prometheus, Grafana, Alertmanager   | `monitoring`        | A initialiser |

Le backend et la base sont initialises a ce stade. Les autres dossiers portent
l'arborescence et un README de cadrage, leur contenu fait l'objet d'un ticket dedie.

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

- Branches : `feat/`, `fix/`, `chore/`, `docs/` suivi d'un libelle court.
- Commits : Conventional Commits, portee = dossier de premier niveau concerne.
- Toute decision structurante donne lieu a un ADR dans `docs/adr`.
