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
| Frontend   | Angular 22, Node 24 LTS             | `apps/frontend`     | Tableau de bord |
| Base       | PostgreSQL 17 + TimescaleDB         | `db`                | Initialise    |
| ETL        | Apache Airflow                      | `etl/airflow`       | A initialiser |
| Infra      | Terraform (k3s single-node)         | `infra/terraform`   | Initialise    |
| Reverse proxy | Nginx, TLS                       | `infra/proxy`       | En place      |
| CI/CD      | GitHub Actions                      | `.github/workflows` | Backend en place |
| Monitoring | Prometheus, Grafana, Alertmanager   | `monitoring`        | A initialiser |
| ML         | LightGBM, MLflow                    | `ml`                | Entrainement initialise |

Le backend, la base et l'infrastructure (Terraform/k3s) sont initialises a ce stade. Le frontend
sert un tableau de bord sur `/dashboard`, dont les données proviennent de fixtures : les endpoints
correspondants restent à écrire côté API. Les autres dossiers portent l'arborescence et un README
de cadrage, leur contenu fait l'objet d'un ticket dedie.

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
├── infra/
│   ├── proxy/          Reverse proxy Nginx : terminaison TLS et routage
│   └── terraform/
│       ├── modules/        Modules reutilisables
│       └── environments/   Racines Terraform, une par environnement
├── ml/                 Pipeline d'entrainement LightGBM, suivi MLflow
├── monitoring/
│   ├── prometheus/     Collecte et regles d'alerte
│   ├── grafana/        Provisioning et dashboards
│   └── alertmanager/   Routage des alertes
├── docs/               ADR et vues d'architecture
└── scripts/            Outillage local
```

## Demarrage

Prerequis : uv, Docker, Node 24 LTS (npm fourni). Le poste doit disposer de Python 3.14, que
`uv` installe seul.

```bash
cp .env.example .env                               # variables de docker-compose
cp apps/backend/.env.example apps/backend/.env     # variables du backend hors conteneur

make db-up     # PostgreSQL + TimescaleDB, publie sur le port 5433
make install   # dependances du backend et du frontend
make migrate   # applique les migrations Alembic
make dev       # backend sur http://localhost:8000 (docs sur /docs), frontend sur http://localhost:4200
make check     # lint + typage + tests
```

`make help` liste les cibles disponibles.

Deux fichiers d'environnement, deux usages : `.env` a la racine alimente `docker-compose.yml`,
`apps/backend/.env` alimente le backend lance sur le poste. Le port 5433 est publie plutot que
5432, souvent deja pris par une autre base.

La boucle de developpement est `make db-up` puis `make dev` : seule la base tourne en
conteneur, le backend et le frontend tournent tous les deux sur le poste, lances ensemble par
`make dev` (logs entrelaces dans le meme terminal, Ctrl+C arrete les deux). `make dev-backend`
et `make dev-frontend` restent disponibles pour lancer un seul des deux. Le service `backend`
du `docker-compose.yml` sert la stack complete et la recette, et n'embarque pas le source, donc
toute modification y demande un `docker compose up -d --build backend`.

Verifier que la base repond et que l'extension est chargee :

```bash
curl -s localhost:8000/api/v1/health/ready
```

## Stack complète derrière le reverse proxy

Pour servir l'application comme sur la machine cible, en HTTPS et sous une seule origine :

```bash
make tls-selfsigned PUBLIC_HOST=enervision.local   # certificat de démonstration
make stack-up PUBLIC_HOST=enervision.local         # nginx en 80/443, rien d'autre n'est publié
```

Le navigateur avertit d'un émetteur inconnu : Let's Encrypt reste hors d'atteinte tant qu'aucun
nom de domaine public ne résout vers la machine. Routage, mode ACME et renouvellement dans
[`infra/proxy/README.md`](infra/proxy/README.md) ; la décision et ses motifs dans
[l'ADR 0007](docs/adr/0007-terminaison-tls-et-reverse-proxy-nginx.md).

## Conventions

- Branches : `feat/`, `fix/`, `chore/`, `docs/`, `test/` suivi d'un libelle court.
- Commits : Conventional Commits, portee = dossier de premier niveau concerne.
- Toute decision structurante donne lieu a un ADR dans `docs/adr`.
- Toute PR qui change un composant met a jour sa vue dans `docs/architecture`, dans la meme PR.
