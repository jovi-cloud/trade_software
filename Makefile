.DEFAULT_GOAL := help
.PHONY: help install dev dev-backend dev-frontend test test-backend test-frontend lint lint-backend \
        lint-frontend format typecheck check migrate migration db-reset types build \
        clean backup

BACKEND  := backend
FRONTEND := frontend

help: ## Show available commands
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- setup ----
install: ## Install backend and frontend dependencies
	cd $(BACKEND) && uv sync
	cd $(FRONTEND) && npm install

# ------------------------------------------------------------------ dev ----
dev: ## Run backend and frontend together (Ctrl-C stops both)
	@./scripts/dev.sh

dev-backend: ## Run the API with autoreload on http://127.0.0.1:8000
	cd $(BACKEND) && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev-frontend: ## Run the Vite dev server on http://localhost:5173
	cd $(FRONTEND) && npm run dev

# ---------------------------------------------------------------- tests ----
test: test-backend test-frontend ## Run all tests

test-backend: ## Run the backend test suite
	cd $(BACKEND) && uv run pytest

test-frontend: ## Run the frontend unit tests
	cd $(FRONTEND) && npm test

test-cov: ## Run backend tests with a coverage report
	cd $(BACKEND) && uv run pytest --cov --cov-report=term-missing

# ----------------------------------------------------------- code quality --
lint: lint-backend lint-frontend ## Lint everything

lint-backend: ## Ruff + mypy + architecture import contracts
	cd $(BACKEND) && uv run ruff check .
	cd $(BACKEND) && uv run mypy
	cd $(BACKEND) && uv run lint-imports

lint-frontend: ## oxlint
	cd $(FRONTEND) && npm run lint

format: ## Auto-format backend and frontend
	cd $(BACKEND) && uv run ruff format . && uv run ruff check --fix .
	cd $(FRONTEND) && npm run format

typecheck: ## Type-check both projects
	cd $(BACKEND) && uv run mypy
	cd $(FRONTEND) && npm run typecheck

check: lint test ## Everything CI would run

# ------------------------------------------------------------- database ----
migrate: ## Apply all pending migrations
	cd $(BACKEND) && uv run alembic upgrade head

migration: ## Create a migration: make migration m="add strategies table"
	@test -n "$(m)" || (echo 'Usage: make migration m="description"'; exit 1)
	cd $(BACKEND) && uv run alembic revision --autogenerate -m "$(m)"

db-history: ## Show migration history
	cd $(BACKEND) && uv run alembic history --verbose

db-reset: ## Delete the database and re-migrate (DESTROYS ALL DATA)
	@printf 'This deletes data/app.db and all results. Type yes to continue: ' && read ans && [ "$$ans" = "yes" ]
	rm -f data/app.db data/app.db-wal data/app.db-shm
	cd $(BACKEND) && uv run alembic upgrade head

# ---------------------------------------------------------------- types ----
types: ## Regenerate frontend API types (backend must be running)
	cd $(FRONTEND) && npm run types

# ---------------------------------------------------------------- build ----
build: ## Production build of the frontend
	cd $(FRONTEND) && npm run build

clean: ## Remove build artifacts and caches (leaves data/ untouched)
	rm -rf $(FRONTEND)/dist $(FRONTEND)/node_modules/.vite
	find $(BACKEND) -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf $(BACKEND)/.pytest_cache $(BACKEND)/.ruff_cache $(BACKEND)/.mypy_cache

backup: ## Archive the data directory
	@./scripts/backup.sh
