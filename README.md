# EnerVision

Monorepo de la plateforme EnerVision : collecte, stockage, analyse et restitution de
series temporelles energetiques, deployee sur une machine on-premise.

## Stack cible

| Domaine    | Technologie                         | Emplacement         | Etat          |
|------------|-------------------------------------|---------------------|---------------|
| Backend    | FastAPI, Python 3.14                | `apps/backend`      | Initialise    |
| Frontend   | Angular, Node 24 LTS                | `apps/frontend`     | A initialiser |
| Base       | PostgreSQL + TimescaleDB            | `db`                | A initialiser |
| ETL        | Apache Airflow                      | `etl/airflow`       | A initialiser |
| Infra      | Terraform                           | `infra/terraform`   | A initialiser |
| CI/CD      | GitHub Actions                      | `.github/workflows` | A initialiser |
| Monitoring | Prometheus, Grafana, Alertmanager   | `monitoring`        | A initialiser |

Seul le backend est initialise a ce stade. Les autres dossiers portent l'arborescence et
un README de cadrage, leur contenu fait l'objet d'un ticket dedie.

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
make install   # dependances du backend
make dev       # API sur http://localhost:8000, docs sur /docs
make check     # lint + typage + tests
```

`make help` liste les cibles disponibles.

## Conventions

- Branches : `feat/`, `fix/`, `chore/`, `docs/` suivi d'un libelle court.
- Commits : Conventional Commits, portee = dossier de premier niveau concerne.
- Toute decision structurante donne lieu a un ADR dans `docs/adr`.
