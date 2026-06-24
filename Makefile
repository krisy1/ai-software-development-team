.PHONY: help install dev build up down migrate lint test clean \
        docker-build docker-up docker-down docker-logs docker-ps \
        docker-restart docker-frontend-logs docker-api-logs

.DEFAULT_GOAL := help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'

# ── Local Development ─────────────────────────────────────────

install: ## Install production dependencies
	cd backend && pip install -r requirements/base.txt

dev: ## Install development dependencies
	cd backend && pip install -r requirements/dev.txt

migrate: ## Run database migrations
	cd backend && alembic upgrade head

migrate-new: ## Create a new migration
	cd backend && alembic revision --autogenerate -m "$(name)"

lint: ## Run linters
	cd backend && ruff check app/ tests/
	cd backend && mypy app/ --ignore-missing-imports

lint-fix: ## Auto-fix lint issues
	cd backend && ruff check --fix app/ tests/

test: ## Run all tests
	cd backend && python -m pytest tests/ -v --cov=app --cov-report=term-missing

test-unit: ## Run unit tests only
	cd backend && python -m pytest tests/unit/ -v

test-integration: ## Run integration tests only
	cd backend && python -m pytest tests/integration/ -v

clean: ## Clean cache and build artifacts
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/

# ── Docker Deployment ─────────────────────────────────────────

docker-build: ## Build all Docker images
	docker compose build

docker-build-no-cache: ## Build all Docker images from scratch
	docker compose build --no-cache

docker-up: ## Start all services in detached mode
	docker compose up -d

docker-up-logs: ## Start all services with attached logs
	docker compose up

docker-down: ## Stop and remove all containers
	docker compose down

docker-down-volumes: ## Stop and remove containers + volumes
	docker compose down -v

docker-restart: ## Restart all services
	docker compose down && docker compose up -d

docker-logs: ## Tail logs from all services
	docker compose logs -f

docker-api-logs: ## Tail API logs
	docker compose logs -f api

docker-worker-logs: ## Tail Celery worker logs
	docker compose logs -f worker

docker-frontend-logs: ## Tail frontend logs
	docker compose logs -f frontend

docker-ps: ## List running containers
	docker compose ps

docker-status: ## Show service health status
	docker compose ps --services --filter "status=running"

docker-infra-up: ## Start only infrastructure (postgres, redis, chromadb)
	docker compose up -d postgres redis chromadb

docker-prebuild: ## Validate Docker configs without building
	docker compose config --quiet

# ── Production Deployment ──────────────────────────────────────

PROD_COMPOSE := -f docker-compose.yml -f docker-compose.prod.yml

ssl-cert: ## Generate self-signed SSL cert for development
	@mkdir -p docker/nginx/ssl
	@openssl req -x509 -nodes -days 365 \
		-newkey rsa:2048 \
		-keyout docker/nginx/ssl/key.pem \
		-out docker/nginx/ssl/cert.pem \
		-subj "/CN=localhost"
	@echo "SSL certificate generated at docker/nginx/ssl/"

prod-build: ## Build production images
	docker compose $(PROD_COMPOSE) build

prod-up: ## Start production stack
	docker compose $(PROD_COMPOSE) up -d

prod-up-logs: ## Start production stack with attached logs
	docker compose $(PROD_COMPOSE) up

prod-down: ## Stop production stack
	docker compose $(PROD_COMPOSE) down

prod-logs: ## Tail production logs
	docker compose $(PROD_COMPOSE) logs -f

prod-ps: ## List production containers
	docker compose $(PROD_COMPOSE) ps
