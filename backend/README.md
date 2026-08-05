# crossbill Backend

Backend API for crossbill - a self-hosted web app to sync highlights from KOReader to a server.

## Features

- FastAPI web framework
- SQLAlchemy 2.0 ORM
- PostgreSQL database with Docker support
- Alembic database migrations
- uv dependency management
- Hexagonal architecture
- Ruff linting
- pytest testing framework
- Strong typing with pyright

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker and Docker Compose (for PostgreSQL)

## Setup

### 1. Start PostgreSQL Database

```bash
docker compose -f docker-compose.dev.yml up -d
```

This starts a PostgreSQL container and Garage on docker. 
Follow main readme for instructions on how to setup them for use in development, especially Garage.

### 2. Install dependencies

```bash
uv sync
```

### 3. Copy environment variables

Copy the example environment file to the project root directory (used by both `docker-compose.yml` and local development):

```bash
cp ../.env.example ../.env
```

For local backend development, you can also source the `.env` file before running commands:

```bash
source ../.env
```

### 4. Run migrations

```bash
make migrate
```

### 5. Run the development server

```bash
make dev-app
make dev-worker
```

The API will be available at http://localhost:8000

## Docker Commands

### Stop the database
```bash
docker-compose stop
```

### Start the database
```bash
docker-compose start
```

### Stop and remove containers (data is preserved in volumes)
```bash
docker-compose down
```

### Remove containers and volumes (⚠️ deletes all data)
```bash
docker-compose down -v
```

### View database logs
```bash
docker-compose logs -f postgres
```

### Access PostgreSQL CLI
```bash
docker-compose exec postgres psql -U crossbill -d crossbill
```

## Development

### Running tests
```bash
make test
```

### Linting and type checking
```bash
make lint
```

### Formatting
```bash
make format
```

### Creating migrations
```bash
make migrate-new msg="description"
make migrate
```

## Create password hash to be saved to the database from password:
```
 uv run python -c "from argon2 import PasswordHasher; ph = PasswordHasher(); print(ph.hash('your_password_here'))"
```

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc
