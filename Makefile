BACKEND := apps/backend

.DEFAULT_GOAL := help
.PHONY: help install dev lint format typecheck test test-cov test-integration check \
        docker-build db-up db-down db-reset db-logs db-psql migrate

help: ## Liste les cibles disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Installe les dependances du backend
	cd $(BACKEND) && uv sync --all-groups

dev: ## Lance l'API en rechargement a chaud
	cd $(BACKEND) && uv run uvicorn app.main:create_app --factory --reload --host 0.0.0.0 --port 8000

lint: ## Analyse statique du backend
	cd $(BACKEND) && uv run ruff check .

format: ## Formate et corrige le backend
	cd $(BACKEND) && uv run ruff format . && uv run ruff check --fix .

typecheck: ## Verifie le typage du backend
	cd $(BACKEND) && uv run mypy app

test: ## Execute les tests backend ne demandant pas de base
	cd $(BACKEND) && uv run pytest --cov-fail-under=85

test-cov: ## Rapports de couverture HTML et XML, plus les resultats au format JUnit
	cd $(BACKEND) && uv run pytest --cov-fail-under=85 --cov-report=html \
		--cov-report=xml --junitxml=test-results/junit.xml

test-integration: ## Execute les tests exigeant une base joignable
	cd $(BACKEND) && uv run pytest -m integration

check: lint typecheck test ## Chaine de verification complete

docker-build: ## Construit l'image du backend
	docker build -t enervision-backend:local $(BACKEND)

db-up: ## Demarre la base PostgreSQL TimescaleDB
	docker compose up -d db

db-down: ## Arrete la base en conservant ses donnees
	docker compose stop db

db-reset: ## Detruit la base et rejoue db/init
	docker compose down -v && docker compose up -d db

db-logs: ## Suit les journaux de la base
	docker compose logs -f db

db-psql: ## Ouvre une session psql sur la base applicative
	docker compose exec db psql -U $${POSTGRES_USER:-enervision} -d $${POSTGRES_DB:-enervision}

migrate: ## Applique les migrations Alembic
	cd $(BACKEND) && uv run alembic upgrade head
