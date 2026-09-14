BACKEND := apps/backend

.DEFAULT_GOAL := help
.PHONY: help install dev lint format typecheck test check docker-build

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

test: ## Execute les tests backend
	cd $(BACKEND) && uv run pytest

check: lint typecheck test ## Chaine de verification complete

docker-build: ## Construit l'image du backend
	docker build -t enervision-backend:local $(BACKEND)
