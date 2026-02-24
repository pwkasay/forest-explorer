.DEFAULT_GOAL := help
STATE ?= NC

.PHONY: help setup down ingest ingest-counties ingest-climate dbt dbt-test dbt-seed test lint format logs

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

setup: ## Start all services (db, backend, frontend)
	docker compose up -d

down: ## Stop all services
	docker compose down

ingest: ## Ingest FIA data (default: STATE=NC)
	docker compose exec backend python -m app.ingestion.fia_loader --state $(STATE)

ingest-counties: ## Ingest county boundaries (default: STATE=NC)
	docker compose exec backend python -m app.ingestion.tiger_loader --state $(STATE)

ingest-climate: ## Ingest PRISM climate normals (default: STATE=NC)
	docker compose exec backend python -m app.ingestion.prism_loader --state $(STATE)

dbt: ## Run dbt models
	docker compose exec backend dbt run --project-dir /app/dbt --profiles-dir /app/dbt

dbt-test: ## Run dbt tests
	docker compose exec backend dbt test --project-dir /app/dbt --profiles-dir /app/dbt

dbt-seed: ## Load seed data (species_ref.csv)
	docker compose exec backend dbt seed --project-dir /app/dbt --profiles-dir /app/dbt

test: ## Run backend tests
	cd backend && pytest

lint: ## Lint and format-check backend
	cd backend && ruff check . && ruff format --check .

format: ## Auto-format backend code
	cd backend && ruff format . && ruff check --fix .

logs: ## Tail backend logs
	docker compose logs -f backend
