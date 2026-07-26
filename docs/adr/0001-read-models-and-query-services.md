# ADR-0001: Read models and query services (CQRS-lite)

- **Status:** Accepted
- **Date:** 2026-07-26
- **Applies to:** `backend/`
- **Migration completed:** 2026-07-26 (all modules)

## Context

The backend is a DDD modular monolith: one bounded context, modules under
`src/domain`, `src/application` and `src/infrastructure`, with strict
domain-module independence enforced by import-linter. The application layer is
allowed to compose across modules.

Repositories currently serve two jobs at once: they manage aggregate lifecycle
(load, mutate, save) *and* they feed views. Because the only available shape is
the aggregate, view-shaped data gets squeezed through aggregate-shaped
interfaces. Two symptoms:

- `HighlightRepositoryProtocol.search` returns
  `list[tuple[Highlight, Book, Chapter | None, list[Tag], list[Flashcard]]]`.
  The tuple is not a domain concept; it is a view row wearing domain clothes.
- `GetBookDetailsUseCase` made roughly seven repository calls to render one
  page, including `search(search_text="", limit=10000)` — loading every
  highlight of a book as a full aggregate, mapping each ORM row through a
  domain entity, then discarding the `Book` element of every tuple. Data that
  nothing mutates travelled ORM → domain entity → Pydantic.

The cost is paid twice: at runtime (aggregates hydrated to be thrown away) and
in the design (repository and use-case interfaces widen to serve rendering
concerns, so aggregate boundaries blur).

## Decision

**Reads and writes get separate models.** The write side is unchanged: router →
command use case → aggregate → repository. The read side gets **query
services**: purpose-built view DTOs served by dedicated ports whose adapters map
ORM rows directly to those DTOs.

### Layout

| Where | What |
| --- | --- |
| `src/application/<module>/queries/` | Frozen view-DTO dataclasses, the query protocol (port), and the read use case that wraps it |
| `src/application/<module>/commands/` | **Commands only** |
| `src/infrastructure/<module>/queries/` | The query adapter. Like repositories and mappers, it MAY import ORM models, and maps rows straight to view DTOs without building domain entities |

A view's query lives in the module that owns the view (book details →
`library`). The infrastructure adapter may import other modules' ORM models to
join across tables. Infrastructure is a single layer and cross-module ORM
imports already happen there (`tag_repository` imports the reading and notes
association tables); this is accepted, and the domain-module independence
contract is unaffected because nothing in `src/domain` is involved.

### Calling convention

**Routers always invoke use cases — reads included.** A read use case is a thin
wrapper around the query port, plus any command that the page legitimately
triggers. For book details that is:

```
router
  └─ GetBookDetailsUseCase            (application/library/queries/)
       ├─ MarkBookViewedUseCase       (application/library/commands/book_management/)
       └─ BookDetailsQueryProtocol    → BookDetailsQuery (infrastructure/library/queries/)
```

The wrapper is deliberate boilerplate. We chose pattern uniformity over
minimalism: a rule with no branches ("routers call use cases") is easier to
follow and to review than one with an exception.

Placing read use cases inside `queries/` rather than alongside the commands is
what makes that uniformity compatible with rule 2 below: `commands/` stays
commands-only,
so the import contract can forbid it from touching read models outright. The
reverse direction — a read use case importing a command use case — is allowed
and is exactly how `GetBookDetailsUseCase` reaches `MarkBookViewedUseCase`.

### Rule 1 — queries never decide

Query adapters may select, join, filter, order and group. They must not encode
business rules. Where a view needs rule-derived data, the adapter reuses the
existing domain or application service on the data it fetched; it never
re-implements the rule in SQL.

`BookDetailsQuery` demonstrates this: highlight labels are resolved by injecting
the existing `LabelResolutionService` rather than re-encoding
`HighlightStyleResolver`'s book-over-global precedence as a `CASE` expression.

This rule is **review-enforced**. There is no static check that distinguishes a
join from a decision; reviewers must ask "is this SQL making a choice the domain
already knows how to make?"

### Rule 2 — read DTOs are dead ends

View DTOs flow to routers and response schemas only. They never become input to
a command. This is **machine-enforced** by the `queries-are-dead-ends`
import-linter contract in `backend/pyproject.toml`, which forbids `src.domain`
and `src.application.*.commands` from importing `src.application.*.queries`.
The wildcard module expressions are supported by import-linter ≥ 2.11, so the
contract covers modules that do not exist yet without further edits.

### Scope

No DB schema changes, no API contract changes. The generated OpenAPI document is
byte-identical to `main` after this spike.

## Alternatives considered

- **Routers calling query ports directly** (no read use case). Fewer moving
  parts, and it makes "reads are different" visible in the code. Rejected: it
  splits the router-level convention in two, and it pushes orchestration —
  book details also stamps `last_viewed` — into the router.
- **Read use cases alongside the commands.** Rejected: it would force the
  dead-ends contract to enumerate individual command modules instead of a whole
  package, which is exactly the kind of list that rots.
- **Widening repositories further** (more tuple-returning finders). Rejected:
  that is the status quo being replaced.

## Explicitly NOT adopted

- **Event sourcing.** Writes remain state-based against the same tables.
- **A separate read store.** No projections, no denormalised tables, no
  eventual consistency. Reads and writes hit the same PostgreSQL database in
  the same request, so a read after a write in the same transaction sees it.
- **A read/write split at the ORM or session level.** One `AsyncSession`,
  injected the same way into repositories and query adapters.

## The halfway option

Direct ORM-to-DTO mapping is the default, but it is not mandatory. A query
service may assemble its DTOs from domain entities returned by existing
repositories where the direct mapping is not worth the duplication — a small
view over a single aggregate, say. What matters is the *interface*: the view is
served by a query port returning view DTOs. How the adapter fills them is an
implementation detail that can be tightened later without touching callers.

## Consequences

**Good**

- View queries are readable as queries. `BookDetailsQuery` issues seven
  targeted selects instead of loading and mapping every aggregate on the page.
- Repositories can shrink back toward aggregate lifecycle. `search` stays for
  now (highlight search still uses it), but it no longer has to also be the
  book-details loader.
- Read paths become cheap to optimise: an adapter can change its joins freely
  because its output type is owned by the view, not by any aggregate.

**Costs**

- Two models for the same tables. A column rename now touches a mapper and an
  adapter.
- Rule 1 is not machine-checkable, so it depends on review discipline.
- The read use-case wrapper is boilerplate by construction.

**Migration**

The app ported view-by-view rather than big-bang, starting with book details;
untouched endpoints kept working through repositories throughout. That
migration is **complete** — every module now has a `queries/` package and no
`use_cases/` package survives. `docs/agents/read-models.md` remains the recipe,
and it now describes adding a view to a migrated codebase rather than porting
one out of a repository.

**Naming**

A module's write side is `commands/` (symmetric with `queries/`). Class names
keep the `*UseCase` suffix on both sides: "use case" is the layer role — reads
are use cases too — while the package encodes the command/query kind. `*Command`
as a class suffix is deliberately avoided (in CQRS literature a Command is a
message object, which is not this codebase's shape). `use_cases/` was the
historical name for the write side and was renamed per module as that module's
last read moved to `queries/`.
