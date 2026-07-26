# Claude Code Project Guidelines

## Type Checking

This project uses **pyright** (not mypy) for type checking. Always run `pyright` to verify type correctness after changes to Python files. Never suggest or run mypy.

```bash
# Backend type checking
cd backend && uv run pyright <file>

# Frontend type checking
cd frontend && npm run type-check
```

## Linting

- **Backend**: Uses `ruff` for linting and formatting
- **Frontend**: Uses `eslint` for linting, `prettier` for formatting

```bash
# Backend linting
cd backend && uv run ruff check <file>

# Frontend linting
cd frontend && npm run lint
```

## Background Worker (SAQ)

The backend includes a background job queue powered by [SAQ](https://github.com/tobymao/saq) with PostgreSQL as the queue backend (no Redis required).

### Running the Worker

```bash
# Development
cd backend && uv run saq src.worker.worker_settings

# Production (Docker) — already configured in docker-compose.yml as `worker` service
saq src.worker.worker_settings
```

### How It Works

- **Job Queue**: SAQ manages job enqueueing, dequeuing (via Postgres LISTEN/NOTIFY), retries, and cancellation. SAQ creates its own tables (`saq_jobs`, `saq_stats`, `saq_versions`) automatically.
- **JobBatch**: A domain entity (`src/domain/jobs/entities/job_batch.py`) tracks groups of related SAQ jobs. For example, generating prereading for all chapters of a book creates one `JobBatch` with N individual SAQ jobs.
- **Worker Process**: Runs as a separate process (`src/worker.py`) using the same Docker image with a different entrypoint command. Creates a fresh DB session per task to avoid sharing sessions across concurrent coroutines.
- **Task Handlers**: Task logic lives in `src/infrastructure/jobs/tasks/`. Each handler class receives dependencies via constructor injection. The worker builds these handlers with fresh sessions per invocation.
- **Batch Progress**: Uses atomic SQL increments (not read-modify-write) to safely update batch progress from concurrent tasks.
- **Concurrency**: Controlled via `WORKER_CONCURRENCY` env var (default: 5).

### Adding New Job Types

1. Add a new value to `JobBatchType` enum in `src/domain/jobs/entities/job_batch.py`
2. Create a task handler in `src/infrastructure/jobs/tasks/`
3. Create a top-level async task function in `src/worker.py` and register it in `worker_settings["functions"]`
4. Create an enqueue use case in `src/application/jobs/use_cases/`
5. Wire it through the DI container (`src/containers/jobs.py`)

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/jobs/books/{book_id}/prereading` | Enqueue batch prereading generation |
| `GET` | `/api/v1/jobs/batches/{batch_id}` | Get batch status |
| `DELETE` | `/api/v1/jobs/batches/{batch_id}` | Cancel a batch |

## Architecture: Domain-Driven Design with Hexagonal/Dependency Injection Patterns

This backend follows DDD (Domain-Driven Design) with hexagonal architecture and dependency injection. **These boundaries are critical and must be strictly enforced:**

### Layer Responsibilities

1. **Domain Layer** (`backend/src/domain/`)
   - Contains domain entities, value objects, and domain services
   - **MUST NOT** depend on ORM models, Pydantic schemas, or any infrastructure
   - Pure business logic only
   - Example: `Book`, `Chapter`, `XPoint` (value objects)

2. **Application Layer** (`backend/src/application/`)
   - Contains use cases (application services)
   - Works with **domain entities**, NOT ORM models
   - Uses repository protocols (interfaces) via dependency injection
   - **MUST NOT** import from infrastructure layer
   - **MUST NOT** return Pydantic schemas - return domain entities

3. **Infrastructure Layer** (`backend/src/infrastructure/`)
   - Contains repository implementations
   - ORM models live **ONLY** here
   - Responsible for all ORM-to-domain and domain-to-ORM conversion
   - Implements repository protocols defined in domain layer

4. **Routers/API Layer** (`backend/src/routers/`)
   - HTTP endpoints
   - Uses use cases via dependency injection
   - Converts between domain entities and Pydantic schemas
   - **MUST NOT** use ORM models directly
   - **MUST NOT** contain business logic

### Read Models (CQRS-lite)

Views are being migrated off the repositories onto **query services**: view DTOs
and a query port in `src/application/<module>/queries/`, an ORM-to-DTO adapter in
`src/infrastructure/<module>/queries/`. `src/application/<module>/use_cases/`
holds **commands only**; read use cases live in the `queries` package and are
what routers inject. Read DTOs must never reach a command — enforced by the
`queries-are-dead-ends` import-linter contract.

- Decision and rationale: `docs/adr/0001-read-models-and-query-services.md`
- Porting recipe for a new view: `docs/agents/read-models.md`
- Reference implementation: the book-details view (`library` module)

### Critical Architectural Rules

1. **ORM Models**
   - ORM models belong **ONLY** in the infrastructure/repository layer
   - **NEVER** import or use ORM models in:
     - Routers
     - Application services (use cases)
     - Domain layer
   - Repositories are responsible for converting between ORM and domain entities

2. **Domain Entities vs ORM Models**
   - Domain entities are in `backend/src/domain/`
   - ORM models are in `backend/src/infrastructure/`
   - Domain entities must NOT depend on SQLAlchemy or ORM models
   - Application services work with domain entities, not ORM models

3. **Value Objects and Pydantic Schemas**
   - Domain value objects (e.g., `XPoint`, `ISBN`) must be converted to primitives before passing to Pydantic models
   - Do NOT pass raw value objects to Pydantic schema fields
   - Example:
     ```python
     # ✗ WRONG
     schema = BookSchema(xpoint=book.xpoint)  # XPoint is a value object

     # ✓ CORRECT
     schema = BookSchema(xpoint=book.xpoint.value)  # Convert to primitive
     ```

4. **SQLAlchemy Query Safety**
   - When using `joinedload()` with collections, always call `.unique()` on the result
   - Example:
     ```python
     # ✓ CORRECT
     result = session.execute(
         select(Book).options(joinedload(Book.chapters))
     ).unique().scalars().all()
     ```

5. **Domain Services**
   - Domain services live in the domain layer, NOT the application layer
   - They encapsulate domain logic that doesn't belong to a single entity
   - Exception: services that compose data *across* domain modules for views (read-model
     assembly, e.g. `HighlightGroupingService`, `BookDetailsAggregation`) are application
     services, not domain services — they live in the application layer

6. **Module Boundaries (enforced by import-linter)**
   - The backend is a single bounded context; the directories under `src/domain/` are
     modules within it (`library`, `reading`, `notes`, `learning`, `tagging`, ...)
   - **Domain layer is strict**: a domain module may import only from itself and
     `src/domain/common/`. Reference another module's aggregates by ID
     (e.g. `tag_ids: list[int]`, `note_id: NoteId`), never by importing its entities
   - **Application layer is relaxed**: use cases may import other modules' repository
     protocols and entities to compose read models — that is the application layer's job
   - Contracts are defined in `backend/pyproject.toml` under `[tool.importlinter]` and run
     via `uv run lint-imports` (in CI and in the post-edit hook). When adding a new domain
     module, add it to the `domain-module-independence` contract's module list

7. **Domain Exceptions**
   - Base exceptions live in `backend/src/domain/common/exceptions.py` (`DomainError`, `EntityNotFoundError`, `ValidationError`, etc.)
   - Each subdomain defines specific subclasses in its own `exceptions.py` (e.g., `domain/reading/exceptions.py`, `domain/learning/exceptions.py`)
   - **Always use specific NotFound subclasses** (e.g., `BookNotFoundError`, `ChapterNotFoundError`) instead of raising `EntityNotFoundError` directly with a string entity type
   - When adding a new entity that can be "not found", create a dedicated subclass:
     ```python
     # ✗ WRONG
     raise EntityNotFoundError("Chapter", chapter_id)

     # ✓ CORRECT
     raise ChapterNotFoundError(chapter_id)
     ```

## Refactoring and Migration Rules

### Before ANY file deletion or module move:

1. **ALWAYS** grep for all imports of the old module path
2. Update all import references before running tests
3. Do NOT consider a migration complete until stale imports are resolved

```bash
# Example: Check for stale imports after moving a service
rg "from.*old_module_path import" backend/
```

### Migration Checklist

When migrating a service to DDD architecture:

1. ✓ Read the migration plan document if one exists
2. ✓ Create domain entities/value objects in domain layer (no ORM dependencies)
3. ✓ Create/update repository in infrastructure layer (all ORM code here only)
4. ✓ Convert application service to work with domain entities, not ORM models
5. ✓ After ANY file deletion/move, grep for old import paths and update them
6. ✓ Ensure value objects are converted to primitives before Pydantic schemas
7. ✓ For SQLAlchemy joinedload collections, use `.unique()`
8. ✓ Run pyright and fix all type errors
9. ✓ Run pytest and fix all test failures
10. ✓ Do NOT declare complete until all checks pass

## Testing

Always run the full test suite after completing any migration or refactoring:

```bash
cd backend && uv run pytest
```

Do not declare work complete until all tests pass. If tests fail, fix them before stopping.

## Working Style

- When a migration plan document exists, follow it precisely
- Do not redesign the architecture or create broader plans unless explicitly asked
- If something in the plan seems wrong, ask before deviating
- After editing files, the post-edit hooks will automatically run linting and type checking

## Common Pitfalls to Avoid

Based on past migrations, watch out for:

1. **ORM Leakage**: Accidentally using ORM models in routers or application services
2. **Stale Imports**: Leaving old import statements after moving/deleting files
3. **Value Object Type Errors**: Passing value objects directly to Pydantic instead of converting to primitives
4. **Missing .unique()**: Forgetting `.unique()` on SQLAlchemy queries with joinedload
5. **Domain Services in Wrong Layer**: Placing domain services in application layer instead of domain layer
6. **Incorrect Return Types**: Application services returning Pydantic schemas instead of domain entities
7. **Generic EntityNotFoundError**: Using `EntityNotFoundError("TypeName", id)` instead of a specific subclass like `ChapterNotFoundError(id)`

## Pre-Commit Validation

The project has automatic hooks that run:
- Ruff (linting)
- Pyright (type checking)

These run automatically after Edit/Write operations. Pay attention to the warnings and errors they surface.

## Agent skills

### Issue tracker

Issues live as GitHub issues in `Crossbill-Highlights/crossbill-web`, driven via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles use their default label strings (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` and one `docs/adr/` at the repo root, both created lazily. See `docs/agents/domain.md`.
