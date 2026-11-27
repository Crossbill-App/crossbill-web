# Backend

Hooks run ruff and pyright on each edited file and import-linter when a turn
ends. The test suite is not hooked: run `uv run pytest` after any migration or
refactor, and before calling work done. Before writing, changing or reviewing
a test, load the `writing-backend-tests` skill.

## Architecture: DDD with hexagonal boundaries

The layers under `src/` are `domain/`, `application/` and `infrastructure/`
(routers live in `infrastructure/<module>/routers/`, DI wiring in
`containers/`), with the usual hexagonal dependency rules. import-linter
enforces them; the contracts are in `pyproject.toml`. What the code does not
show:

- **ORM models live only in infrastructure.** Repositories convert ORM ↔
  domain. Routers convert domain entities ↔ Pydantic schemas; use cases return
  domain entities, never Pydantic.
- **Value objects → primitives before Pydantic**:
  `BookSchema(xpoint=book.xpoint.value)`, not
  `BookSchema(xpoint=book.xpoint)`.
- **`joinedload()` with collections needs `.unique()`** on the result.
- **Domain services live in the domain layer** — except services that assemble
  read models across modules (e.g. `LabelResolutionService`), which are
  application services by design; query adapters may inject them to reuse a
  rule rather than re-encode it in SQL.
- **Domain modules are strict, the application layer is deliberately relaxed**:
  a domain module (`library`, `reading`, `notes`, `learning`, `tagging`, …)
  imports only itself and `domain/common/`, referencing other modules'
  aggregates by ID (`tag_ids: list[int]`); application-layer use cases *may*
  import other modules' protocols and entities to compose read models. When
  adding a domain module, add it to the `domain-module-independence` contract's
  module list.
- **Raise specific NotFound subclasses** (`BookNotFoundError`), not
  `EntityNotFoundError("Book", id)`. Base exceptions are in
  `src/domain/common/exceptions.py`; each subdomain has its own
  `exceptions.py` — add a subclass there for each new not-foundable entity.

## Read models (CQRS-lite)

A new read starts in `src/application/<module>/queries/` (view DTOs + query
port + read use case; ORM-to-DTO adapter in
`src/infrastructure/<module>/queries/`). `commands/` holds commands only, and
read DTOs stay out of commands — the `queries-are-dead-ends` contract enforces
it. A read too small to deserve a port still lives in `queries/`, delegating
to a repository and returning domain entities (the ADR's "halfway option").

Before adding or porting a view, read the recipe,
`docs/agents/read-models.md`; the decision and its rationale are in
`docs/adr/0001-read-models-and-query-services.md`.
