.PHONY: help test mutation-test duplication-check dev-app dev-worker migrate migrate-new lint format api-client release-nightly deploy empty-s3-bucket reset-db clone-production-db

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# Backend commands (run from repo root)

test: ## Run backend tests
	cd backend && uv run pytest

mutation-test: ## Run mutation-testing audit on the backend domain layer (slow, ~5-10 min)
	cd backend && ./scripts/patch-mutmut.sh
	cd backend && rm -rf mutants && uv run mutmut run
	cd backend && uv run mutmut results

# Copy/paste detector (jscpd v5, the Rust engine). It is a devDependency of the
# frontend workspace, so `npm ci` at the repo root hoists the binary into
# ./node_modules/.bin and npx finds it from anywhere in the tree.
# Config lives in backend/.jscpd.json; it fails once duplication passes the
# threshold recorded there, which is a ratchet: lower it as duplication drops,
# never raise it. The frontend equivalent is `npm run duplication-check`.
# Output is the compact `ai` reporter; add `--reporters console` for the
# detailed view with columns and token counts.
duplication-check: ## Report copy-paste duplication in the backend (jscpd)
	cd backend && npx jscpd --no-tips

api-client: ## Export the OpenAPI schema and regenerate the frontend API client (no running backend needed)
	cd backend && uv run python scripts/export_openapi.py
	cd frontend && npm run api:generate

dev-app: ## Run the backend dev server
	cd backend && uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

dev-worker: ## Run the SAQ background worker
	cd backend && uv run saq src.worker.worker_settings

migrate: ## Run database migrations (alembic upgrade head)
	cd backend && uv run alembic upgrade head

migrate-new: ## Create a new migration (usage: make migrate-new msg="description")
	cd backend && uv run alembic revision --autogenerate -m "$(msg)"

lint: ## Run ruff linter and pyright type checker on backend
	cd backend && uv run ruff check .
	cd backend && uv run pyright
	cd backend && uv run --no-sync lint-imports

lint-fix: ## Run ruff linter and pyright type checker on backend
	cd backend && uv run ruff check --fix .
	cd backend && uv run pyright
	cd backend && uv run --no-sync lint-imports
	cd backend && uv run ruff format .

format: ## Format backend code with ruff
	cd backend && uv run ruff format .

release-nightly: ## Build and push nightly Docker image to Docker Hub
	./scripts/build-for-docker-hub.sh

# Builds+pushes a uniquely-tagged nightly image and deploys it via the Railway API
# (plain `railway redeploy` reuses the cached digest, so it won't pull a new build).
# Requires RAILWAY_API_TOKEN (railway.com -> Account -> Tokens; NOT RAILWAY_TOKEN).
# No `railway login` needed — the script talks to the API directly.
deploy: ## Build+push nightly image and deploy it to Railway
	set -a; [ -f .env.deploy ] && . ./.env.deploy; set +a; ./scripts/railway-deploy.sh

empty-s3-bucket: ## Remove all objects from the local S3 bucket
	aws --endpoint-url http://localhost:3900 s3 rm s3://crossbill-files --recursive

# Reads the same git-ignored .env.deploy as `deploy` (RAILWAY_API_TOKEN and
# RAILWAY_ENVIRONMENT_ID); the Postgres service itself is discovered via the API.
# DESTRUCTIVE: drops the local database. Pass flags with ARGS, e.g.
# `make clone-production-db ARGS="--yes --no-migrate"` (see --help).
clone-production-db: ## Replace the local dev database with a clone of production (destructive)
	set -a; [ -f .env.deploy ] && . ./.env.deploy; set +a; ./scripts/clone-production-db.sh $(ARGS)

reset-db: ## Reset the database (removes volume and re-runs migrations)
	docker compose -f docker-compose.dev.yml down -v postgres
	docker compose -f docker-compose.dev.yml up -d postgres
	@echo "Waiting for PostgreSQL to accept connections..."
	@until docker compose -f docker-compose.dev.yml exec postgres psql -U crossbill -d crossbill -c "SELECT 1" > /dev/null 2>&1; do sleep 1; done
	$(MAKE) migrate
