BACKEND := apps/backend
FRONTEND := apps/frontend
ML := ml
AIRFLOW := etl/airflow
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
AIRFLOW_PORT := $(or $(strip $(call env-val,AIRFLOW_PORT)),8080)
MAILPIT_UI_PORT := $(or $(strip $(call env-val,MAILPIT_UI_PORT)),8025)
ML_DATABASE_URL ?= postgresql+psycopg://$(PG_USER):$(PG_PASSWORD)@localhost:$(PG_PORT)/$(PG_DB)
export ML_DATABASE_URL

# Le jeu historique s'arrete au 31/12/2024 : score et detection ancres a l'horloge reelle ne
# verraient qu'un parc muet depuis des mois. Cf. `--now` de enervision_ml.score.
DEMO_NOW ?= 2024-12-31T00:00:00Z

.DEFAULT_GOAL := help
.PHONY: help install install-backend install-frontend install-ml install-airflow \
        dev dev-backend dev-frontend \
        lint format typecheck test test-cov test-integration check \
        openapi docker-build db-up db-down db-reset db-logs db-psql db-wait db-ensure-airflow \
        migrate bootstrap-admin services-up demo-data demo-data-force \
        ml-lint ml-typecheck ml-test ml-check ml-train ml-score detect-alerts recommendations \
        airflow-lint airflow-test airflow-check airflow-up airflow-down airflow-logs \
        tls-selfsigned tls-acme tls-renew stack-up stack-down stack-logs

help: ## Liste les cibles disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

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

ml-train: ## Entraine le modele LightGBM. CSV=chemin optionnel, sinon lit ML_DATABASE_URL
	cd $(ML) && uv run python -m enervision_ml.train $(if $(CSV),--csv $(CSV),)

ml-score: ## Score le prochain pas horaire et l'ecrit dans `prediction`. CSV= et NOW= optionnels
	cd $(ML) && uv run python -m enervision_ml.score $(if $(CSV),--csv $(CSV),) $(if $(NOW),--now $(NOW),)

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
	$(COMPOSE_PROD) up -d --build
	$(COMPOSE_PROD) exec -T backend alembic upgrade head

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
