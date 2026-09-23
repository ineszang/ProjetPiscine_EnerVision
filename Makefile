BACKEND := apps/backend
FRONTEND := apps/frontend
ML := ml
AIRFLOW := etl/airflow
E2E := tests/e2e
COMPOSE_PROD := docker compose -f docker-compose.yml -f docker-compose.prod.yml

# Piège : sans `export`, une valeur passée en ligne de commande n'atteindrait pas docker compose.
# PUBLIC_HOST retombe sur le `.env`, que make ne lit pas, puis sur la valeur de `.env.example`.
PUBLIC_HOST ?= $(shell sed -n 's/^PUBLIC_HOST=//p' .env 2>/dev/null | tail -1)
PUBLIC_HOST := $(or $(strip $(PUBLIC_HOST)),enervision.local)
export PUBLIC_HOST
ifdef ACME_EMAIL
export ACME_EMAIL
endif

# Piege : make ne lit pas `.env`, que seul docker compose interpole. Les cibles hors conteneur
# (ml-*, demo-data, db-wait) joignent la base par le port publie et ont besoin de ces valeurs.
env-val = $(shell sed -n 's/^$(1)=//p' .env 2>/dev/null | tail -1)
PG_USER := $(or $(strip $(call env-val,POSTGRES_USER)),enervision)
PG_PASSWORD := $(or $(strip $(call env-val,POSTGRES_PASSWORD)),change_me)
PG_DB := $(or $(strip $(call env-val,POSTGRES_DB)),enervision)
PG_PORT := $(or $(strip $(call env-val,POSTGRES_PORT)),5433)
ml-env-val = $(shell sed -n 's/^$(1)=//p' ml/.env 2>/dev/null | tail -1)
ML_ENV_DB_PASSWORD := $(call ml-env-val,MLFLOW_DB_PASSWORD)
AIRFLOW_PORT := $(or $(strip $(call env-val,AIRFLOW_PORT)),8080)
MAILPIT_UI_PORT := $(or $(strip $(call env-val,MAILPIT_UI_PORT)),8025)
ML_DATABASE_URL ?= postgresql+psycopg://$(PG_USER):$(PG_PASSWORD)@localhost:$(PG_PORT)/$(PG_DB)
export ML_DATABASE_URL

# Piege : la base des tests d'integration n'est pas la base de developpement. Ces tests ecrivent
# et suppriment des lignes, et leurs fixtures refusent de demarrer ailleurs que sur
# `enervision_test` (garde sur le nom, cf. ml/tests/conftest.py).
PG_TEST_DB ?= enervision_test
TEST_DATABASE_URL ?= postgresql+asyncpg://$(PG_USER):$(PG_PASSWORD)@localhost:$(PG_PORT)/$(PG_TEST_DB)
ML_TEST_DATABASE_URL ?= postgresql+psycopg://$(PG_USER):$(PG_PASSWORD)@localhost:$(PG_PORT)/$(PG_TEST_DB)

# Piege : ni make ni ces cibles ne lisent `.env` pour COMPOSE_PROFILES, que docker compose y lit
# seul. `stack-up` le relit ici pour savoir s'il doit poser le role `supervision` apres migration.
SUPERVISION := $(findstring monitoring,$(COMPOSE_PROFILES) $(call env-val,COMPOSE_PROFILES))
SERVICES_SUPERVISION := prometheus alertmanager grafana postgres-exporter node-exporter cadvisor
GRAFANA_PORT := $(or $(strip $(call env-val,GRAFANA_PORT)),3001)
PROMETHEUS_PORT := $(or $(strip $(call env-val,PROMETHEUS_PORT)),9090)
supervision-garde = for cle in APP_METRICS_TOKEN GRAFANA_ADMIN_PASSWORD SUPERVISION_DB_PASSWORD; do \
		sed -n "s/^$$cle=//p" .env 2>/dev/null | tail -1 | grep -q . \
			|| { echo "$$cle manquant dans .env, requis par la supervision (cf. .env.example)"; exit 1; }; \
	done
MONITORING := docker compose --profile monitoring
PROMTOOL := $(MONITORING) run --rm --no-deps --entrypoint promtool prometheus

# Piege : `e2e-prepare` ajoute trois sites `demo-*` et des comptes `test-*` a la base visee. Elle
# vise la base de `make dev` ; ne jamais la lancer contre la recette ou la prod.
E2E_COMPTES ?= $(CURDIR)/$(E2E)/.comptes.json
E2E_API ?= http://localhost:$(or $(strip $(call env-val,BACKEND_PORT)),8000)

# Piege : `run` ne demarre que k6, la stack doit deja tourner. `--user` fait ecrire les rapports
# de tests/load/results avec l'uid du poste, pas celui de l'image (12345), qui n'y a pas acces.
k6-run = mkdir -p tests/load/results && $(COMPOSE_PROD) --profile load run --rm \
	--user "$$(id -u):$$(id -g)" -e K6_WEB_DASHBOARD=true \
	-e K6_WEB_DASHBOARD_EXPORT=/results/$(1)-$$(date +%Y%m%dT%H%M%S).html \
	k6 run /scripts/$(1).js

# Le jeu historique s'arrete au 31/12/2024 : score et detection ancres a l'horloge reelle ne
# verraient qu'un parc muet depuis des mois. Cf. `--now` de enervision_ml.score.
DEMO_NOW ?= 2024-12-31T00:00:00Z

.DEFAULT_GOAL := help
.PHONY: help install install-backend install-frontend install-ml install-airflow \
        dev dev-backend dev-frontend \
        lint format typecheck test test-cov test-integration ml-test-integration \
        test-chaine check \
        openapi docker-build db-up db-down db-reset db-logs db-psql db-wait db-ensure-airflow \
        migrate migrate-test bootstrap-admin services-up demo-data demo-data-force \
        ml-lint ml-typecheck ml-test ml-check ml-train ml-score mlflow-up detect-alerts recommendations \
        airflow-lint airflow-test airflow-check airflow-up airflow-down airflow-logs \
        tls-selfsigned tls-acme tls-renew tls-duckdns front-up stack-up stack-down stack-logs \
        e2e-install e2e-prepare e2e load-smoke load-test load-stress load-limits \
        db-ensure-supervision monitoring-up monitoring-down monitoring-logs monitoring-check

help: ## Liste les cibles disponibles
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: install-backend install-frontend install-ml install-airflow ## Installe les dépendances backend, frontend, ML et Airflow

install-backend: ## Installe les dépendances du backend
	cd $(BACKEND) && uv sync --all-groups

install-frontend: ## Installe les dépendances du frontend
	cd $(FRONTEND) && npm ci

install-ml: ## Installe les dépendances du pipeline ML
	cd $(ML) && uv sync --all-groups

install-airflow: ## Installe les dépendances de lint/test des DAGs Airflow
	cd $(AIRFLOW) && uv sync --all-groups

dev: services-up migrate demo-data ## Lance toute la stack : base, Mailpit, Airflow, puis backend et frontend
	@echo "airflow  -> http://localhost:$(AIRFLOW_PORT)  mailpit -> http://localhost:$(MAILPIT_UI_PORT)"
	@trap 'kill 0' EXIT INT TERM; \
	$(MAKE) --no-print-directory dev-backend & \
	$(MAKE) --no-print-directory dev-frontend & \
	wait

services-up: ## Démarre les services conteneurisés dont `make dev` dépend (base, Mailpit, Airflow)
	docker compose up -d db mailpit
	@$(MAKE) --no-print-directory db-wait
	@$(MAKE) --no-print-directory db-ensure-airflow
	docker compose up -d airflow-init airflow-apiserver airflow-scheduler airflow-dag-processor

dev-backend: ## Lance l'API seule en rechargement à chaud
	@echo "backend  -> http://localhost:8000 (docs sur /docs)"
	cd $(BACKEND) && uv run uvicorn app.main:create_app --factory --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Lance le frontend seul en rechargement à chaud
	@echo "frontend -> http://localhost:4200"
	cd $(FRONTEND) && npm start

lint: ## Analyse statique du backend
	cd $(BACKEND) && uv run ruff check .

format: ## Formate et corrige le backend
	cd $(BACKEND) && uv run ruff format . && uv run ruff check --fix .

typecheck: ## Vérifie le typage du backend
	cd $(BACKEND) && uv run mypy app

test: ## Exécute les tests backend ne demandant pas de base
	cd $(BACKEND) && uv run pytest --cov-fail-under=85

test-cov: ## Rapports de couverture HTML et XML, plus les résultats au format JUnit
	cd $(BACKEND) && uv run pytest --cov-fail-under=85 --cov-report=html \
		--cov-report=xml --junitxml=test-results/junit.xml

test-integration: ## Exécute les tests exigeant une base joignable
	cd $(BACKEND) && uv run pytest -m integration

check: lint typecheck test ## Chaîne de vérification complète

openapi: ## Régénère apps/backend/openapi.json depuis les routes déclarées
	cd $(BACKEND) && uv run python -m app.cli export-openapi

ml-lint: ## Analyse statique du pipeline ML
	cd $(ML) && uv run ruff check .

ml-typecheck: ## Vérifie le typage du pipeline ML
	cd $(ML) && uv run mypy enervision_ml tests

ml-test: ## Exécute les tests du pipeline ML (donnees synthetiques, sans base ni serveur MLflow)
	cd $(ML) && uv run pytest

ml-check: ml-lint ml-typecheck ml-test ## Chaîne de vérification complète du pipeline ML

# La cible surcharge ML_DATABASE_URL, que ce Makefile exporte vers la base de développement : la
# garde du conftest ferait échouer la cible sans cette surcharge.
ml-test-integration: ML_DATABASE_URL := $(ML_TEST_DATABASE_URL)
ml-test-integration: ## Tests ML exigeant une base migrée. Faire `make db-up migrate-test` avant
	cd $(ML) && uv run pytest -m integration --no-cov

test-chaine: ## Chaîne ML -> DB -> API, vrais binaires. Exige les deux environnements uv
	cd $(BACKEND) && DATABASE_URL=$(TEST_DATABASE_URL) ML_PYTHON=$(CURDIR)/$(ML)/.venv/bin/python \
		uv run pytest -m chaine --no-cov

ml-train: ## Entraine le modele LightGBM. CSV=chemin optionnel, sinon lit ML_DATABASE_URL
	cd $(ML) && uv run python -m enervision_ml.train $(if $(CSV),--csv $(CSV),)

ml-score: ## Score le prochain pas horaire et l'ecrit dans `prediction`. CSV= et NOW= optionnels
	cd $(ML) && uv run python -m enervision_ml.score $(if $(CSV),--csv $(CSV),) $(if $(NOW),--now $(NOW),)

mlflow-up: ## Démarre le serveur MLflow (tracking + registry) en conteneur. ml/.env requis
	@test -n "$(strip $(ML_ENV_DB_PASSWORD))" \
		|| { echo "MLFLOW_DB_PASSWORD absente de ml/.env (copier ml/.env.example)"; exit 1; }
	@echo "$(ML_ENV_DB_PASSWORD)" | grep -qE '^[A-Za-z0-9]+$$' \
		|| { echo "MLFLOW_DB_PASSWORD doit contenir uniquement lettres et chiffres (interpolee dans l'URI postgresql://)"; exit 1; }
	cd $(ML) && docker compose -f docker-compose.mlflow.yml up -d --build
	@echo "mlflow   -> http://localhost:5000"

detect-alerts: ## Détecte les alertes internes depuis les lectures en base. SITE= et NOW= optionnels
	cd $(BACKEND) && uv run python -m app.detection.internal_alerts $(if $(SITE),--site-id $(SITE),) $(if $(NOW),--now $(NOW),)

recommendations: ## Genere les recommandations depuis les alertes en base. SITE=identifiant optionnel
	cd $(BACKEND) && uv run python -m app.cli generate-recommendations $(if $(SITE),--site-id $(SITE),)

airflow-lint: ## Analyse statique des DAGs Airflow
	cd $(AIRFLOW) && uv run ruff check .

airflow-test: ## Verifie que les DAGs s'importent sans erreur et ont la structure attendue
	cd $(AIRFLOW) && uv run pytest

airflow-check: airflow-lint airflow-test ## Chaîne de vérification complète des DAGs Airflow

airflow-up: db-ensure-airflow ## Démarre Airflow (api-server + scheduler + dag-processor, LocalExecutor). db-up requis avant.
	docker compose up -d airflow-init airflow-apiserver airflow-scheduler airflow-dag-processor
	@echo "airflow  -> http://localhost:$${AIRFLOW_PORT:-8080}"

airflow-down: ## Arrête l'api-server, le scheduler et le dag-processor Airflow
	docker compose stop airflow-apiserver airflow-scheduler airflow-dag-processor

airflow-logs: ## Suit les journaux du scheduler Airflow (où tournent les tâches, LocalExecutor)
	docker compose logs -f airflow-scheduler

docker-build: ## Construit l'image du backend
	docker build -t enervision-backend:local $(BACKEND)

tls-selfsigned: ## Génère le certificat de démonstration. PUBLIC_HOST=..., FORCE=1 pour écraser
	./scripts/tls-selfsigned.sh $(if $(FORCE),--force,)

# Piège : l'image backend ne migre pas au démarrage, et `/health/ready` ne teste que la connexion
# et l'extension. Sans `alembic upgrade head`, la stack démarre verte sur une base sans schéma.
stack-up: ## Démarre la stack derrière le reverse proxy, puis migre la base. PUBLIC_HOST=... au besoin
	@test -f infra/proxy/tls/fullchain.pem \
		|| { echo "Aucun certificat dans infra/proxy/tls. Lancer d'abord make tls-selfsigned"; exit 1; }
	@openssl x509 -in infra/proxy/tls/fullchain.pem -noout -checkhost "$(PUBLIC_HOST)" >/dev/null \
		|| { echo "Le certificat ne couvre pas $(PUBLIC_HOST). Relancer make tls-selfsigned PUBLIC_HOST=$(PUBLIC_HOST) FORCE=1"; exit 1; }
	@$(if $(SUPERVISION),$(supervision-garde),true)
	$(COMPOSE_PROD) up -d --build
	$(COMPOSE_PROD) exec -T backend alembic upgrade head
	@$(if $(SUPERVISION),$(MAKE) --no-print-directory db-ensure-supervision,true)

stack-down: ## Arrête la stack complète en conservant les données
	$(COMPOSE_PROD) stop

stack-logs: ## Suit les journaux du reverse proxy
	$(COMPOSE_PROD) logs -f proxy

tls-acme: ## Demande un certificat Let's Encrypt. PUBLIC_HOST public et ACME_EMAIL requis
	@test "$(PUBLIC_HOST)" != enervision.local \
		|| { echo "PUBLIC_HOST doit être un domaine public résolvable, pas le nom de démonstration"; exit 1; }
	$(COMPOSE_PROD) --profile acme run --rm certbot certonly --webroot -w /var/www/certbot \
		-d $(PUBLIC_HOST) \
		--email $${ACME_EMAIL:?ACME_EMAIL=... requis} \
		--agree-tos --no-eff-email --deploy-hook /deploy-hook.sh
	$(COMPOSE_PROD) exec proxy nginx -s reload

tls-renew: ## Renouvelle les certificats Let's Encrypt et recharge le proxy
	$(COMPOSE_PROD) --profile acme run --rm certbot renew --deploy-hook /deploy-hook.sh
	$(COMPOSE_PROD) exec proxy nginx -s reload

# Pourquoi : la VM n'a qu'une IP privée, que Let's Encrypt ne joint pas ; le défi DNS-01 passe
# par l'API DuckDNS (ADR 0018). Le jeton transite par l'environnement, jamais par `argv`.
ACME_SH := neilpang/acme.sh:3.1.6
DUCKDNS_TOKEN_FILE ?= $(abspath $(CURDIR)/../duckdns.token)
acme-sh = docker run --rm --user "$$(id -u):$$(id -g)" -e DuckDNS_Token -e AUTO_UPGRADE=0 \
	-v "$(CURDIR)/infra/proxy/acme:/acme.sh" -v "$(CURDIR)/infra/proxy/tls:/tls" $(ACME_SH)

# acme.sh sort en 2 quand le certificat n'est pas encore à renouveler : rejouable à chaque déploiement.
tls-duckdns: ## Certificat Let's Encrypt par DNS-01 DuckDNS, renouvelé seulement à échéance
	@case "$(PUBLIC_HOST)" in *.duckdns.org) ;; *) echo "PUBLIC_HOST=$(PUBLIC_HOST) n'est pas un nom DuckDNS"; exit 1 ;; esac
	@test -r "$(DUCKDNS_TOKEN_FILE)" || { echo "Jeton DuckDNS illisible : $(DUCKDNS_TOKEN_FILE)"; exit 1; }
	@mkdir -p infra/proxy/acme
	@DuckDNS_Token="$$(cat "$(DUCKDNS_TOKEN_FILE)")"; export DuckDNS_Token; \
		$(acme-sh) --issue --server letsencrypt --dns dns_duckdns -d "$(PUBLIC_HOST)"; \
		code=$$?; [ $$code -eq 0 ] || [ $$code -eq 2 ] || exit $$code
	@$(acme-sh) --install-cert --ecc -d "$(PUBLIC_HOST)" \
		--fullchain-file /tls/fullchain.pem --key-file /tls/privkey.pem
	@$(COMPOSE_PROD) exec -T proxy nginx -s reload 2>/dev/null \
		|| echo "Proxy arrêté : il lira le certificat à son démarrage"

front-up: ## Démarre ou recharge le frontal SNI de la VM, sur les ports 80 et 443 de l'hôte
	docker compose -f infra/front/compose.yml up -d
	docker compose -f infra/front/compose.yml exec -T front nginx -s reload

e2e-install: ## Installe Playwright et Chromium pour les tests de bout en bout
	cd $(E2E) && npm ci && npx playwright install chromium

e2e-prepare: ## Sème le jeu de démonstration et crée les comptes de test sur la base de `make dev`
	docker compose exec -T db psql -U $(PG_USER) -d $(PG_DB) -v ON_ERROR_STOP=1 < db/seeds/demo.sql
	cd $(BACKEND) && BASE_URL=$(E2E_API) COMPTES_FICHIER=$(E2E_COMPTES) ADMIN_SUPPLEMENTAIRE=1 \
		../../scripts/comptes-test.sh

e2e: ## Joue les parcours Playwright. E2E_BASE_URL= optionnel (défaut http://localhost:4200)
	cd $(E2E) && E2E_COMPTES=$(E2E_COMPTES) npx playwright test

load-smoke: ## Tir k6 d'une minute. K6_EMAIL= et K6_PASSWORD= d'un lecteur, K6_BASE_URL= optionnel
	$(call k6-run,smoke)

load-test: ## Charge nominale k6, 50 utilisateurs pendant 8 minutes. Rapport HTML dans tests/load/results
	$(call k6-run,charge)

load-stress: ## Monte le débit jusqu'à la rupture de l'API. Sur la VM, la prod partage la machine
	$(call k6-run,stress)

load-limits: ## Vérifie par le proxy que nginx limite le débit d'une même adresse (429)
	$(call k6-run,limitation-debit)

# Piege : le mot de passe est lu dans `.env` par le shell et passe a psql sur son entree
# standard. Developpe par make, il apparaitrait en clair dans la ligne de commande (`ps`).
db-ensure-supervision: ## Crée ou réaligne le rôle `supervision`, en lecture seule, de Grafana et de l'exportateur
	@mdp="$$(sed -n 's/^SUPERVISION_DB_PASSWORD=//p' .env 2>/dev/null | tail -1)"; \
	[ -n "$$mdp" ] || { echo "SUPERVISION_DB_PASSWORD manquant dans .env"; exit 1; }; \
	{ printf '\\set mot_de_passe %s\n' "$$mdp"; cat db/roles/supervision.sql; } \
		| docker compose exec -T db psql -U $(PG_USER) -d $(PG_DB) -v ON_ERROR_STOP=1 -v base=$(PG_DB) -q

monitoring-up: ## Démarre la supervision sur la stack en cours : Prometheus, Alertmanager, Grafana, exporteurs
	@$(supervision-garde)
	$(MONITORING) up -d --no-deps $(SERVICES_SUPERVISION)
	@$(MAKE) --no-print-directory db-ensure-supervision
	@echo "grafana -> http://localhost:$(GRAFANA_PORT)  prometheus -> http://localhost:$(PROMETHEUS_PORT)"

monitoring-down: ## Arrête la supervision en conservant ses données
	$(MONITORING) stop $(SERVICES_SUPERVISION)

monitoring-logs: ## Suit les journaux de Prometheus, Alertmanager et Grafana
	$(MONITORING) logs -f prometheus alertmanager grafana

monitoring-check: ## Valide la configuration de supervision et joue les tests des règles d'alerte, comme la CI
	$(PROMTOOL) check config /etc/prometheus/prometheus.yml
	$(PROMTOOL) test rules /etc/prometheus/tests/enervision.test.yml
	$(MONITORING) run --rm --no-deps --entrypoint amtool alertmanager check-config /etc/alertmanager/alertmanager.yml
	@for tableau in monitoring/grafana/dashboards/*.json; do jq empty "$$tableau" || exit 1; done

db-up: ## Démarre la base PostgreSQL TimescaleDB
	docker compose up -d db

db-down: ## Arrête la base en conservant ses données
	docker compose stop db

db-reset: ## Détruit la base et rejoue db/init
	docker compose down -v && docker compose up -d db

db-logs: ## Suit les journaux de la base
	docker compose logs -f db

db-psql: ## Ouvre une session psql sur la base applicative
	docker compose exec db psql -U $${POSTGRES_USER:-enervision} -d $${POSTGRES_DB:-enervision}

db-wait: ## Attend que la base accepte les connexions
	@for _ in $$(seq 1 60); do \
		docker compose exec -T db pg_isready -U $(PG_USER) -d $(PG_DB) >/dev/null 2>&1 && exit 0; \
		sleep 1; \
	done; \
	echo "La base n'accepte toujours pas de connexion apres 60s"; exit 1

# Piege : db/init ne rejoue qu'a la premiere initialisation du volume. Un `pgdata` cree avant
# db/init/120-airflow-database.sql n'a pas de base `airflow`, et airflow-init boucle dessus.
db-ensure-airflow: ## Crée la base de métadonnées Airflow si le volume pgdata est antérieur à db/init/120
	@docker compose exec -T db psql -U $(PG_USER) -d postgres -tAc \
		"SELECT 1 FROM pg_database WHERE datname = 'airflow'" | grep -q 1 \
		|| docker compose exec -T db psql -U $(PG_USER) -d postgres -c "CREATE DATABASE airflow"

migrate: ## Applique les migrations Alembic
	cd $(BACKEND) && uv run alembic upgrade head

migrate-test: ## Applique les migrations sur enervision_test, la base des tests d'intégration
	cd $(BACKEND) && DATABASE_URL=$(TEST_DATABASE_URL) uv run alembic upgrade head

bootstrap-admin: ## Crée le premier administrateur, mot de passe saisi au clavier
	cd $(BACKEND) && uv run python -m app.cli create-admin --email $${EMAIL:?EMAIL=... requis}

demo-data: ## Renseigne prédictions, alertes et recommandations si elles manquent. NOW= optionnel
	@nombre=$$(docker compose exec -T db psql -U $(PG_USER) -d $(PG_DB) -tAc 'SELECT count(*) FROM alert') \
		|| { echo "demo-data : base injoignable ou migrations non appliquees"; exit 1; }; \
	if [ "$$nombre" = 0 ]; then \
		$(MAKE) --no-print-directory demo-data-force; \
	else \
		echo "demo-data : $$nombre alerte(s) deja en base (make demo-data-force pour rejouer)"; \
	fi

demo-data-force: ## Rejoue le peuplement sans regarder l'existant. Les trois etapes sont idempotentes
	$(MAKE) --no-print-directory ml-score NOW=$(DEMO_NOW)
	$(MAKE) --no-print-directory detect-alerts NOW=$(DEMO_NOW)
	$(MAKE) --no-print-directory recommendations
