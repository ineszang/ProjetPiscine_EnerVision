# EnerVision

Monorepo de la plateforme EnerVision : collecte, stockage, analyse et restitution de
series temporelles energetiques, deployee sur une machine on-premise.

## Jalons

| Jalon | Intitulé |
|-------|----------------------------------------------------------|
| J1    | Valider la préparation de l'environnement et du repo     |
| J2    | Valider le périmètre retenu et les choix technologiques  |
| J3    | Ingestion & backend                                      |
| J4    | Architecture, sécurité & frontend                        |
| J5    | Valider la robustesse et assurer les livrables           |
| J6    | Amélioration possible                                    |

Ce que la documentation apporte à chacun : [docs/architecture/00-vue-ensemble.md](docs/architecture/00-vue-ensemble.md).

## Stack cible

| Domaine    | Technologie                         | Emplacement         | Etat          |
|------------|-------------------------------------|---------------------|---------------|
| Backend    | FastAPI, Python 3.14                | `apps/backend`      | En place    |
| Frontend   | Angular 22, Node 26                 | `apps/frontend`     | En place |
| Base       | PostgreSQL 17 + TimescaleDB         | `db`                | En place    |
| ETL        | Apache Airflow                      | `etl/airflow`       | Cinq DAGs     |
| Infra      | Terraform (k3s single-node)         | `infra/terraform`   | Initialise    |
| Reverse proxy | Nginx, TLS                       | `infra/proxy`       | En place      |
| CI/CD      | GitHub Actions                      | `.github/workflows` | En place |
| Monitoring | Prometheus, Grafana, Alertmanager   | `monitoring`        | A initialiser |
| ML         | LightGBM, MLflow                    | `ml`                | En place |

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
│   ├── dags/           DAGs d'orchestration (pipeline ML, alertes, imports historique et API Mock)
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

make install   # dependances du backend, du frontend, du ML et des DAGs
make dev       # toute la stack, voir ci-dessous
make check     # lint + typage + tests
```

`make dev` enchaine tout : demarrage des services conteneurises (base sur le port 5433, Mailpit,
Airflow), migrations Alembic, peuplement de demonstration si les alertes manquent, puis backend
et frontend en rechargement a chaud sur le poste.

| Service | Adresse |
|---|---|
| Backend | <http://localhost:8000> (documentation sur `/docs`) |
| Frontend | <http://localhost:4200> |
| Airflow | <http://localhost:8080> (`AIRFLOW_ADMIN_USERNAME` / `AIRFLOW_ADMIN_PASSWORD` du `.env`) |
| Mailpit | <http://localhost:8025> |

Le `.env` doit porter les cles Airflow avant le premier `make dev` : `AIRFLOW_FERNET_KEY`,
`AIRFLOW_API_SECRET_KEY`, `AIRFLOW_JWT_SECRET`, `AIRFLOW_APP_SECRET_KEY` et
`AIRFLOW_ADMIN_PASSWORD`. Sans elles `airflow-init` refuse de demarrer, et `airflow-apiserver`,
`airflow-scheduler` et `airflow-dag-processor` avec lui.

Les cibles d'origine restent disponibles pour ne demarrer qu'une partie : `make db-up`,
`make airflow-up`, `make dev-backend`, `make dev-frontend`.

`make help` liste les cibles disponibles.

Deux fichiers d'environnement, deux usages : `.env` a la racine alimente `docker-compose.yml`,
`apps/backend/.env` alimente le backend lance sur le poste. Le port 5433 est publie plutot que
5432, souvent deja pris par une autre base.

Le backend et le frontend tournent sur le poste, lances ensemble par `make dev` (logs
entrelaces dans le meme terminal, Ctrl+C arrete les deux) ; la base, Mailpit et Airflow tournent
en conteneur. Le service `backend` du `docker-compose.yml` sert la stack complete et la recette,
et n'embarque pas le source, donc toute modification y demande un
`docker compose up -d --build backend`.

### Donnees de demonstration

Le jeu historique s'arrete au 31/12/2024. `make demo-data` renseigne les tables que les vues
alertes, recommandations et previsions lisent, en ancrant le scoring et la detection a cette
date (`DEMO_NOW`) plutot qu'a l'horloge reelle, qui ne verrait qu'un parc muet depuis des mois.
La cible ne fait rien si des alertes existent deja ; `make demo-data-force` rejoue les trois
etapes, toutes idempotentes en base.

Un volume `pgdata` cree avant `db/init/120-airflow-database.sql` n'a pas de base `airflow` :
`db/init` ne rejoue qu'a la premiere initialisation. `make db-ensure-airflow`, appelee par
`make dev` et `make airflow-up`, la cree au besoin, sans detruire les donnees applicatives.

Verifier que la base repond et que l'extension est chargee :

```bash
curl -s localhost:8000/api/v1/health/ready
```

## Stack complète derrière le reverse proxy

Pour servir l'application comme sur la machine cible, en HTTPS et sous une seule origine.
L'overlay emploie `!override` et `!reset`, donc **Docker Compose 2.24.4 ou plus récent** :

```bash
make tls-selfsigned PUBLIC_HOST=enervision.local   # certificat de démonstration
make stack-up PUBLIC_HOST=enervision.local         # nginx en 80/443, rien d'autre n'est publié
```

Le navigateur avertit d'un émetteur inconnu : Let's Encrypt reste hors d'atteinte tant qu'aucun
nom de domaine public ne résout vers la machine. Routage, mode ACME et renouvellement dans
[`infra/proxy/README.md`](infra/proxy/README.md) ; la décision et ses motifs dans
[l'ADR 0007](docs/adr/0007-terminaison-tls-et-reverse-proxy-nginx.md).

Sur la VM ENI, deux environnements cohabitent, recette sur `dev` et production sur `main`,
chacun dans son dossier et son projet Compose : `scripts/provision-host.sh` les prépare, le
workflow `deploy.yml` les redéploie à chaque push par un runner auto-hébergé. Ports, noms
d'hôte et garde-fous dans [`docs/architecture/10-infra.md`](docs/architecture/10-infra.md) et
[l'ADR 0009](docs/adr/0009-deux-environnements-compose-sur-la-vm-eni.md).

## Conventions

- Branches : `feat/`, `fix/`, `chore/`, `docs/`, `test/` suivi d'un libelle court.
- Commits : Conventional Commits, portee = dossier de premier niveau concerne.
- Toute decision structurante donne lieu a un ADR dans `docs/adr`.
- Toute PR qui change un composant met a jour sa vue dans `docs/architecture`, dans la meme PR.
