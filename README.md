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

## Stack

| Domaine    | Technologie                         | Emplacement         | Etat          |
|------------|-------------------------------------|---------------------|---------------|
| Backend    | FastAPI, Python 3.14                | `apps/backend`      | En place    |
| Frontend   | Angular 22, Node 26                 | `apps/frontend`     | En place |
| Base       | PostgreSQL 17 + TimescaleDB         | `db`                | En place    |
| ETL        | Apache Airflow                      | `etl/airflow`       | Sept DAGs     |
| Infra      | Terraform (VM ENI ; module k3s)     | `infra/terraform`   | VM appliquée, k3s écrit non appliqué |
| Reverse proxy | Nginx, TLS, frontal SNI          | `infra/proxy`, `infra/front` | En place, certificats Let's Encrypt |
| CI/CD      | GitHub Actions                      | `.github/workflows` | En place |
| Monitoring | Prometheus, Grafana, Alertmanager   | `monitoring`        | En place, profil Compose |
| Stockage objet | Garage (S3), un par environnement | `infra/garage`      | En place, archives de `reading` |
| Tests e2e et de charge | Playwright, k6              | `tests`             | En place |
| ML         | LightGBM, MLflow                    | `ml`                | En place |

Toutes ces briques tournent sur la machine du groupe, en trois environnements (production,
recette, dev). Le frontend sert le tableau de bord, les vues sites, recommandations et
supervision des capteurs, toutes branchées sur l'API réelle : les fixtures sont coupées
(`useMockFixtures: false`). Le module Terraform k3s reste une cible, écrite et validée, jamais
appliquée.

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
│   ├── roles/          Roles PostgreSQL hors schema (supervision)
│   └── seeds/          Jeu de demonstration des tests
├── etl/airflow/
│   ├── dags/           DAGs d'orchestration (pipeline ML, alertes, imports, dérive, rétention)
│   ├── plugins/        Operateurs et hooks maison
│   ├── include/        Requetes SQL et ressources des DAGs
│   └── tests/          Tests d'integrite des DAGs
├── infra/
│   ├── front/          Frontal SNI de la machine : ports 80 et 443, aiguillage par nom
│   ├── garage/         Stockage objet S3 : configuration sans secret
│   ├── proxy/          Reverse proxy Nginx : terminaison TLS et routage
│   └── terraform/
│       ├── modules/        Modules reutilisables
│       └── environments/   Racines Terraform, une par environnement
├── ml/                 Pipeline d'entrainement LightGBM, suivi MLflow
├── monitoring/
│   ├── prometheus/     Collecte et regles d'alerte
│   ├── grafana/        Provisioning et dashboards
│   └── alertmanager/   Routage des alertes
├── tests/
│   ├── e2e/            Parcours Playwright contre la stack
│   ├── garage/         Tests de fumée S3 joués par la CI contre Garage
│   └── load/           Scenarios de charge k6
├── docs/               ADR, vues d'architecture, runbook de pilotage, livrables de rendu
└── scripts/            Outillage local
```

## Demarrage

Prerequis : uv, Docker, Node 26 (version de la CI et de l'image frontend, npm fourni). Le poste doit disposer de Python 3.14, que
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
`airflow-scheduler` et `airflow-dag-processor` avec lui. Il doit aussi porter les six clés
`GARAGE_*` (rpc, jetons, clé S3, clé SSE-C) : `make services-up` refuse sinon de démarrer Garage,
où le DAG `retention` archive les mesures anciennes ([ADR 0019](docs/adr/0019-stockage-objet-garage-et-cycle-de-vie-des-mesures.md)).

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
make stack-up PUBLIC_HOST=enervision.local         # nginx en 80/443, le reste sur 127.0.0.1
```

Le navigateur avertit d'un émetteur inconnu : sur le poste, le certificat est auto-signé. Sur la
machine, les certificats viennent de Let's Encrypt par défi DNS-01
([ADR 0018](docs/adr/0018-noms-publics-certificats-dns01-et-frontal-sni.md)). Routage, mode ACME et renouvellement dans
[`infra/proxy/README.md`](infra/proxy/README.md) ; la décision et ses motifs dans
[l'ADR 0007](docs/adr/0007-terminaison-tls-et-reverse-proxy-nginx.md).

Sur la VM ENI, trois environnements cohabitent, production sur `main`, recette sur `dev`, et
`dev` pour toute autre branche lancée à la main
([ADR 0017](docs/adr/0017-environnement-dev-a-la-demande.md)), chacun dans son dossier et son
projet Compose, derrière un frontal SNI commun : `scripts/provision-host.sh` les prépare, le
workflow `deploy.yml` les redéploie par un runner auto-hébergé, une fois la CI du commit poussé
verte ([ADR 0014](docs/adr/0014-pipeline-ci-unique-et-deploiement-conditionne.md)). Ports, noms
d'hôte et garde-fous dans [`docs/architecture/10-infra.md`](docs/architecture/10-infra.md) et
[l'ADR 0009](docs/adr/0009-deux-environnements-compose-sur-la-vm-eni.md).

## Tests de bout en bout, charge et supervision

| Besoin | Commandes | Détail |
|---|---|---|
| Parcours utilisateur (Playwright) | `make e2e-install`, puis `make e2e-prepare e2e` contre `make dev` | [`tests/e2e/README.md`](tests/e2e/README.md) |
| Tir de charge (k6) | `make load-smoke`, `load-test`, `load-stress`, `load-limits` | [`tests/load/README.md`](tests/load/README.md) |
| Supervision | `make monitoring-up`, Grafana sur <http://localhost:3001> | [`monitoring/README.md`](monitoring/README.md) |

La CI joue les parcours, un tir de fumée et le contrôle de la limitation de débit à chaque PR
qui touche l'application, contre la stack de prod derrière le proxy
([ADR 0015](docs/adr/0015-tests-e2e-et-de-charge-contre-la-stack-compose.md)). La supervision
est active en prod, à la demande ailleurs
([ADR 0016](docs/adr/0016-supervision-en-profil-compose.md)).

## Conventions

- Branches : `feat/`, `fix/`, `chore/`, `docs/`, `test/` suivi d'un libelle court.
- Commits : Conventional Commits, portee = dossier de premier niveau concerne.
- Toute decision structurante donne lieu a un ADR dans `docs/adr`.
- Toute PR qui change un composant met a jour sa vue dans `docs/architecture`, dans la meme PR.
