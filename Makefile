BACKEND := apps/backend
FRONTEND := apps/frontend

.DEFAULT_GOAL := help
.PHONY: help install install-backend install-frontend dev dev-backend dev-frontend \
        lint format typecheck test test-cov test-integration check \
        openapi docker-build db-up db-down db-reset db-logs db-psql migrate bootstrap-admin

help: ## Liste les cibles disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: install-backend install-frontend ## Installe les dépendances backend et frontend

install-backend: ## Installe les dépendances du backend
	cd $(BACKEND) && uv sync --all-groups

install-frontend: ## Installe les dépendances du frontend
	cd $(FRONTEND) && npm ci

dev: ## Lance toute la stack (backend + frontend) en rechargement à chaud
	@trap 'kill 0' EXIT INT TERM; \
	$(MAKE) --no-print-directory dev-backend & \
	$(MAKE) --no-print-directory dev-frontend & \
	wait

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

docker-build: ## Construit l'image du backend
	docker build -t enervision-backend:local $(BACKEND)

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

migrate: ## Applique les migrations Alembic
	cd $(BACKEND) && uv run alembic upgrade head

bootstrap-admin: ## Crée le premier administrateur, mot de passe saisi au clavier
	cd $(BACKEND) && uv run python -m app.cli create-admin --email $${EMAIL:?EMAIL=... requis}
