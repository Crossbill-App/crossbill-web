# Claude Code Project Guidelines

## Type Checking

This project uses **pyright** (not mypy). Run `pyright` after changing Python
files; never suggest or run mypy.

## Architecture: DDD with hexagonal boundaries

The backend layers under `backend/src/` are `domain/`, `application/`,
`infrastructure/`, and `routers/`, with the usual hexagonal dependency rules —
import-linter enforces them mechanically (contracts in `backend/pyproject.toml`,
run by CI and a Stop hook). What you can't infer from the code:

- **ORM models live only in infrastructure.** Repositories convert ORM ↔
  domain. Routers convert domain entities ↔ Pydantic schemas; use cases return
  domain entities, never Pydantic.
- **Value objects → primitives before Pydantic**:
  `BookSchema(xpoint=book.xpoint.value)`, never
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
- **Raise specific NotFound subclasses** (`BookNotFoundError`), never
  `EntityNotFoundError("Book", id)`. Base exceptions:
  `backend/src/domain/common/exceptions.py`; each subdomain has its own
  `exceptions.py` — add a subclass there for each new not-foundable entity.

### Read models (CQRS-lite)

A new read starts in `src/application/<module>/queries/` (view DTOs + query
port + read use case; ORM-to-DTO adapter in
`src/infrastructure/<module>/queries/`). `commands/` holds commands only, and
read DTOs must never reach a command — enforced by the `queries-are-dead-ends`
contract. A read too small to deserve a port still lives in `queries/`,
delegating to a repository and returning domain entities (the ADR's "halfway
option").

- Decision and rationale: `docs/adr/0001-read-models-and-query-services.md`
- Recipe for a new view: `docs/agents/read-models.md` (reference
  implementation: the book-details view, `library` module)

## Testing

Run the full test suite after any migration or refactoring; do not declare work
complete until it passes. Test policy (API-first tiering, assertion depth, when
unit tests are warranted): load the `writing-tests` skill before writing or
reviewing tests.

## Duplication (jscpd)

`make duplication-check` (backend) and `npm run duplication-check` (frontend)
run jscpd; CI fails once duplicated lines pass the `threshold` in the
respective `.jscpd.json`. The threshold is a **ratchet** — it may fall, never
rise. When a refactor drops the percentage, lower the threshold in the same
commit; never raise it to make the check pass — extract the shared code
instead. A Stop hook (`.claude/hooks/check-duplication.sh`) flags clones
overlapping lines the current turn changed. Narrow a scan when only one area
matters:

```bash
cd backend && npx jscpd --no-tips --reporters console src/application/notes
```

There is deliberately no jscpd MCP server: it runs the older v4 engine, whose
numbers disagree with the v5 CLI that the hook and CI run.

## Working Style

- When a migration plan document exists, follow it precisely; if something in
  it seems wrong, ask before deviating.
- Do not redesign the architecture or create broader plans unless explicitly
  asked.
- On bigger tasks, make small, logically separated commits.
- Porting a legacy service onto the architecture: load the `ddd-migration`
  skill.

## Agent docs

- **Issue tracker**: GitHub issues in `Crossbill-Highlights/crossbill-web` via
  the `gh` CLI — `docs/agents/issue-tracker.md`.
- **Triage labels**: the five canonical roles use their default label strings —
  `docs/agents/triage-labels.md`.
- **Domain docs**: single-context — one `CONTEXT.md` and one `docs/adr/` at the
  repo root, created lazily — `docs/agents/domain.md`.
