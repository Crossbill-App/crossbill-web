# Claude Code Project Guidelines

## Type Checking

This project uses **pyright** (not mypy) for type checking. Always run `pyright` to verify type correctness after changes to Python files. Never suggest or run mypy.

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

Views are served by **query services**, not repositories: view DTOs and a query
port in `src/application/<module>/queries/`, an ORM-to-DTO adapter in
`src/infrastructure/<module>/queries/`. `src/application/<module>/commands/`
holds **commands only**; read use cases live in the `queries` package and are
what routers inject. Read DTOs must never reach a command — enforced by the
`queries-are-dead-ends` import-linter contract.

Every module has been migrated, so a **new read starts in `queries/`** — there
is no `use_cases/` package left to put it in. A read too small to deserve a
port still lives there, delegating to a repository and returning domain
entities (the ADR's "halfway option").

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

2. **Value Objects and Pydantic Schemas**
   - Domain value objects (e.g., `XPoint`, `ISBN`) must be converted to primitives before passing to Pydantic models
   - Do NOT pass raw value objects to Pydantic schema fields
   - Example:
     ```python
     # ✗ WRONG
     schema = BookSchema(xpoint=book.xpoint)  # XPoint is a value object

     # ✓ CORRECT
     schema = BookSchema(xpoint=book.xpoint.value)  # Convert to primitive
     ```

3. **SQLAlchemy Query Safety**
   - When using `joinedload()` with collections, always call `.unique()` on the result
   - Example:
     ```python
     # ✓ CORRECT
     result = session.execute(
         select(Book).options(joinedload(Book.chapters))
     ).unique().scalars().all()
     ```

4. **Domain Services**
   - Domain services live in the domain layer, NOT the application layer
   - They encapsulate domain logic that doesn't belong to a single entity
   - Exception: services that compose data *across* domain modules for views (read-model
     assembly, e.g. `LabelResolutionService`) are application services, not domain
     services — they live in the application layer, and query adapters may inject them
     to reuse a rule rather than re-encode it in SQL

5. **Module Boundaries (enforced by import-linter)**
   - The backend is a single bounded context; the directories under `src/domain/` are
     modules within it (`library`, `reading`, `notes`, `learning`, `tagging`, ...)
   - **Domain layer is strict**: a domain module may import only from itself and
     `src/domain/common/`. Reference another module's aggregates by ID
     (e.g. `tag_ids: list[int]`, `note_id: NoteId`), never by importing its entities
   - **Application layer is relaxed**: use cases may import other modules' repository
     protocols and entities to compose read models — that is the application layer's job
   - Contracts are defined in `backend/pyproject.toml` under `[tool.importlinter]` and run
     via `uv run lint-imports` in CI — the post-edit hook does *not* run it, so run it
     yourself after touching imports. When adding a new domain module, add it to the
     `domain-module-independence` contract's module list

6. **Domain Exceptions**
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

The full porting procedure lives in the `ddd-migration` skill.

## Testing

Always run the full test suite after completing any migration or refactoring. Do not
declare work complete until all tests pass. If tests fail, fix them before stopping.
Test policy (API-first tiering, assertion depth, when unit tests are warranted): load the
`writing-tests` skill before writing or reviewing tests.

## Working Style

- When a migration plan document exists, follow it precisely
- Do not redesign the architecture or create broader plans unless explicitly asked
- If something in the plan seems wrong, ask before deviating

## Agent skills

### Issue tracker

Issues live as GitHub issues in `Crossbill-Highlights/crossbill-web`, driven via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles use their default label strings (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` and one `docs/adr/` at the repo root, both created lazily. See `docs/agents/domain.md`.
