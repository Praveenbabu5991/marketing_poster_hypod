.PHONY: help setup dev dev-backend dev-frontend test build up down logs clean migrate

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Local Development ---

setup: ## Install all dependencies (backend + frontend)
	cd backend && uv sync --dev
	cd frontend && npm install

dev: ## Start both backend and frontend for local development
	@echo "Starting backend on :8000 and frontend on :3000..."
	@make dev-backend &
	@make dev-frontend

dev-backend: ## Start backend dev server (port 8000)
	cd backend && uv run uvicorn app.main:app --reload --port 8000

dev-frontend: ## Start frontend dev server (port 3000)
	cd frontend && npm run dev

test: ## Run backend tests
	cd backend && uv run pytest tests/ -v

test-cov: ## Run backend tests with coverage
	cd backend && uv run pytest tests/ -v --cov=app --cov=agents --cov=brand --cov-report=html

migrate: ## Run database migrations (local)
	cd backend && uv run alembic upgrade head

# --- Docker ---

build: ## Build all Docker images
	docker compose build

up: ## Build, start all services, and run migrations
	docker compose up -d --build
	@echo ""
	@echo "Services starting..."
	@echo "  PostgreSQL: localhost:5432"
	@echo "  Backend:    http://localhost:8000 (migrations run automatically)"
	@echo "  Frontend:   http://localhost:3000"

down: ## Stop all services
	docker compose down

logs: ## Follow backend logs
	docker compose logs -f backend

logs-all: ## Follow all service logs
	docker compose logs -f

restart: ## Rebuild and restart all services
	docker compose down
	docker compose up -d --build

# --- Cleanup ---

clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf frontend/dist frontend/node_modules/.cache
	rm -rf backend/htmlcov backend/.coverage backend/.pytest_cache
