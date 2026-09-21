# Infrastructure

Deux topologies coexistent et ne servent pas la même chose. Ce document dit laquelle vaut dans
quel contexte, quelles décisions sont arrêtées, et ce qui manque encore entre les deux.

| Topologie | Sert à | Statut |
|---|---|---|
| Docker Compose | Développer et recetter sur le poste | `Fait` |
| k3s single-node | Déployer sur le serveur on-premise | `En cours` |

## Poste de développement

Statut : `Fait`. Défini par `docker-compose.yml`, projet `enervision`.

```mermaid
flowchart TB
  subgraph poste["Poste de développement"]
    ng["ng serve<br/>:4200"]
    api["uvicorn --reload<br/>:8000"]
  end

  subgraph compose["docker compose"]
    back["service backend<br/>image construite depuis apps/backend"]
    db[("service db<br/>timescale/timescaledb-ha:pg17")]
  end

  ng -.->|"proxy /api"| api
  api -->|"hôte :5433 vers conteneur :5432"| db
  back -->|"réseau interne, db:5432"| db
```

| Service | Image | Points notables |
|---|---|---|
| `db` | `timescale/timescaledb-ha:pg17` | Publié sur **5433** côté hôte, 5432 souvent déjà pris. `healthcheck` `pg_isready`, 12 tentatives, `start_period` 40s |
| `backend` | Construite depuis `apps/backend` | `depends_on: db, condition: service_healthy`. **N'embarque pas le source** : toute modification impose `docker compose up -d --build backend` |

**La boucle de développement n'utilise pas le service `backend`.** `make db-up` puis `make dev` :
seule la base tourne en conteneur, l'API et `ng serve` tournent sur le poste avec le rechargement
à chaud, lancés ensemble par `make dev` (`make dev-backend`/`make dev-frontend` pour lancer l'un
des deux seul). Le service `backend` sert la stack complète et la recette. Les deux occupent le
port 8000, ils ne se lancent donc pas ensemble.

Deux pièges sont documentés en tête du `docker-compose.yml`, ils ne se devinent pas :

- `PGDATA` vaut `/home/postgres/pgdata/data` pour l'image `-ha`, et non le chemin habituel de
  l'image `postgres`. Monté ailleurs, le volume ne retient rien, sans le moindre message.
- `db/init` est monté **fichier par fichier**. Monter le dossier masquerait les scripts d'init de
  l'image, dont `timescaledb-tune`. Ajouter un fichier dans `db/init/` impose donc une ligne dans
  le compose. Voir [`db/README.md`](../../db/README.md).

### Airflow (`ml_train`/`ml_score`, issue #115)

Trois services, `docker compose profiles` non utilisés (démarrage explicite via `make
airflow-up`, pas dans `make dev`) :

| Service | Rôle | Points notables |
|---|---|---|
| `airflow-init` | Migre la base de métadonnées, crée le compte admin | Conteneur jetable (`restart: "no"`), ne redémarre jamais. `webserver`/`scheduler` attendent qu'il se termine avec succès |
| `airflow-webserver` | UI, port `8080` | `LocalExecutor` : n'exécute aucune tâche lui-même |
| `airflow-scheduler` | Planifie et **exécute** les tâches (`LocalExecutor`) | Les DAGs y tournent en sous-processus (`uv run --frozen --no-dev python -m enervision_ml...`), c'est lui qui a besoin du volume `airflow_ml_state` |

Construits depuis `etl/airflow/Dockerfile`, contexte `.` (racine du repo, pas `etl/airflow/`) :
l'image doit pouvoir `COPY` `ml/pyproject.toml`/`ml/uv.lock`/`ml/enervision_ml` pour se
synchroniser un second environnement Python **3.14** (`/opt/ml/.venv`, `uv sync --locked` à la
construction), distinct du Python 3.12 qui fait tourner Airflow lui-même. Les DAGs shellent vers
ce venv plutôt que d'importer LightGBM/MLflow dans le process Airflow.

Piège à connaître : sur un volume `pgdata` déjà peuplé (poste de dev existant plutôt que premier
`make db-up`), `db/init/120-airflow-database.sql` ne se rejoue pas (PostgreSQL n'exécute
`docker-entrypoint-initdb.d/` que sur un volume vide). Créer la base `airflow` à la main une fois :
`docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "CREATE DATABASE airflow;"`.

`libgomp1` est installé explicitement dans l'image (`apt-get`, en root) : l'image Airflow de base
est minimale et n'embarque pas la runtime OpenMP dont LightGBM a besoin, sans quoi l'erreur
(`OSError: libgomp.so.1`) n'apparaît qu'à la première tâche réellement exécutée, pas à la
construction de l'image.

## Cible de déploiement

Statut : `En cours`. Le module `infra/terraform/modules/k3s/` installe le cluster. Il n'a jamais
été appliqué.

```mermaid
flowchart LR
  poste["Poste<br/>terraform apply"]
  kube["kubeconfig local"]

  subgraph serveur["Serveur on-premise"]
    k3s["k3s server single-node<br/>Traefik désactivé"]
    charges["Charges de travail<br/>aucune déclarée"]
  end

  poste -->|"SSH, get.k3s.io"| k3s
  k3s -->|"cat /etc/rancher/k3s/k3s.yaml"| kube
  k3s -.-> charges
```

### Ce que le Terraform fait

```mermaid
sequenceDiagram
  participant TF as terraform apply
  participant SRV as Serveur on-premise
  participant L as Poste local

  TF->>SRV: SSH, curl get.k3s.io puis install server
  TF->>SRV: attend /etc/rancher/k3s/k3s.yaml
  TF->>SRV: ssh cat k3s.yaml
  SRV-->>L: kubeconfig, 127.0.0.1 réécrit en ssh_host
```

### Ce que le Terraform ne fait pas

Il déclare le provider `null` et **lui seul** : ni `kubernetes`, ni `helm`. Aucun namespace,
aucun déploiement, aucun service, aucun ingress. À l'issue d'un `apply`, on dispose d'un cluster
vide et d'un kubeconfig, rien de plus.

## Décisions figées

Ces arbitrages sont pris. Ils ne vivaient jusqu'ici que dans des commentaires de code et des
`description` de variables, c'est-à-dire qu'ils ne survivaient pas au premier remaniement.

| Décision | Raison | Où elle est appliquée |
|---|---|---|
| k3s single-node plutôt que Kubernetes complet | Une seule machine on-premise, pas de plan de contrôle à répartir | `modules/k3s/main.tf` |
| `k3s_version` obligatoire, valeur vide refusée | Sans épinglage, `get.k3s.io` installe la dernière version à chaque exécution : le déploiement cesse d'être reproductible | `validation` dans `modules/k3s/variables.tf` |
| Traefik désactivé | Le choix d'ingress reste ouvert, on ne veut pas en subir un par défaut | `k3s_disable_components`, défaut `["traefik"]` |
| Kubeconfig laissé en `600/root`, lu par `sudo` | `--write-kubeconfig-mode 644` exposerait `cluster-admin` à tout utilisateur local de la machine | Commentaire et `fetch_kubeconfig` dans `modules/k3s/main.tf` |
| State Terraform en backend `local` | Un seul opérateur, pas d'exécution concurrente, pas de dépendance à un stockage distant | `environments/dev/versions.tf` |
| `.terraform.lock.hcl` versionné | Fige les versions de provider entre contributeurs et future CI | Commentaire dans `.gitignore` |
| `*.tfvars` ignoré, `*.tfvars.example` versionné | Les tfvars portent l'adresse du serveur et le chemin de la clé | `.gitignore` |
| Désinstallation gérée au `destroy` | `k3s-uninstall.sh` en `on_failure = continue` : un serveur injoignable ne bloque pas le `destroy` | `modules/k3s/main.tf` |
| Deux racines, `dev` et `prod` | Séparation des états et des variables par environnement | `environments/` |

## Ports et noms

| Quoi | Valeur | Remarque |
|---|---|---|
| PostgreSQL, côté hôte | `5433` | Redirigé vers 5432 dans le conteneur. 5432 est souvent déjà pris |
| PostgreSQL, côté réseau Compose | `db:5432` | Nom de service, utilisé par `DATABASE_URL` du service `backend` |
| API | `8000` | Identique en conteneur et hors conteneur |
| Frontend, `ng serve` | `4200` | Valeur par défaut d'`APP_CORS_ORIGINS`. Le compose n'a aucun service frontend |
| SSH du serveur | `22` par défaut | `ssh_port`, redéfinissable |
| Base applicative | `enervision` | Variable `POSTGRES_DB` |
| Base de test | `enervision_test` | Créée par `db/init/110-test-database.sql`, nom attendu en dur par `apps/backend/tests/conftest.py` |
| Base de métadonnées Airflow | `airflow` | Créée par `db/init/120-airflow-database.sql`, même conteneur `db` |
| Webserver Airflow | `8080` | `make airflow-up`. Scheduler et webserver ne publient que ce port ; les tâches (`LocalExecutor`) tournent côté scheduler, sans port propre |

## Le trou entre les deux topologies

Rien ne relie aujourd'hui ce qui est construit par Compose et ce qui tournerait sur k3s. Compose
construit une image backend localement ; k3s ne saurait pas où la trouver. C'est la première
question à trancher, avant toute ressource Kubernetes.

## Questions ouvertes

- **Quel ingress** remplace Traefik, et qui termine le TLS.
- **Quel registre d'images**, et comment il est alimenté sans CI.
- **Quel stockage persistant** côté Kubernetes pour PostgreSQL, et si la base tourne dans le
  cluster ou à côté.
- **Quelle stratégie de sauvegarde et de restauration** des données de mesure.
- **Que devient `environments/prod/`**, aujourd'hui réduit à un `.gitkeep`.
