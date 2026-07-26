---
name: migrate-read-models
description: Migrate one backend module's reads to the read-model pattern (ADR-0001) — port views to query services, move simple reads to queries/, rename use_cases/ to commands/ when the module empties of reads. Invoke with the module name, e.g. /migrate-read-models tagging.
---

# Migrate a module's reads to read models

The module to migrate is given in the arguments (one of: `tagging`, `reflection`,
`jobs`, `notes`, `learning`, `library`, `identity`, `reading`). If no module is given, list
each module's remaining read use cases and ask which to migrate. Migrate ONE
module per invocation; the shared touch points (the import-linter contract,
`tests/protocol_conformance.py`) conflict across parallel branches, so the
previous module's PR should be merged first.

Read these before touching anything, in order: `CLAUDE.md`,
`docs/adr/0001-read-models-and-query-services.md`, `docs/agents/read-models.md`.
The reference implementation is the book-details view (files listed at the top
of the guide). Work on a branch `read-models-<module>` off origin/main, directly
in the checkout — no git worktrees. Commit in small logical commits; do not push
or open a PR until the user has reviewed the result.

## Steps

### 1. Inventory

List every read use case in `src/application/<module>/use_cases/` and the
endpoint each serves (follow the routers and containers). Include the inventory
with a per-view decision in your final report.

### 2. Port each read

Apply the guide's qualification test:

- **Qualifies** (multi-repository assembly, tuple-returning finders, aggregates
  loaded then partly discarded, limit-10000-style calls) → full port per the
  recipe: frozen DTOs + query protocol + ORM adapter + read use case in
  `queries/`.
- **Simple read** (one `find_by_id` / one list + a mapper) → still MOVE the read
  use case into `queries/`, but use the ADR's "halfway option": it may keep
  delegating to the existing repository and returning domain entities. No
  adapter, no invented DTOs. The goal is that `use_cases/` ends commands-only;
  the goal is NOT ceremony for trivial reads.
- A read that hides a write (timestamps, mark-as-viewed) → extract the write
  into its own command use case under `use_cases/` first.

### 3. Close out the module

If `use_cases/` now contains only commands, rename the directory to `commands/`
per the ADR's end-state naming plan: update all imports and containers, keep the
`*UseCase` class suffix, and extend the `queries-are-dead-ends` contract's
source wildcard to cover BOTH `src.application.*.use_cases` AND
`src.application.*.commands` (other modules still use the old name). If any read
could not move, leave the name alone and say why in the report.

### 4. Shrink the write side

Delete repository methods and services that are now fully dead — `rg` every
candidate first. Tuple-returning finders only die when their last consumer is
ported; never break another module's view.

### 5. Guard rails

Add every new query adapter to `backend/tests/protocol_conformance.py`. Write
adapter tests per the guide's Tests section (ownership isolation and
soft-deletion filters at minimum).

### 6. Verify (all must pass)

- `uv run pytest`
- `uv run pyright` — whole project, what CI runs, not just `src`
- `uv run ruff check src tests` and `uv run ruff format --check src tests`
- `uv run lint-imports`
- OpenAPI document byte-identical to a clean main checkout (endpoint docstrings
  are published API — do not edit them)
- No DB schema changes

### 7. Improve the docs

If the guide or ADR was ambiguous or wrong on something you hit, resolve it and
amend the doc in the same branch — the docs are the migration's memory.

## Report

The inventory with decisions (full port / halfway / stayed + why), adapter query
counts vs the old path, judgment calls, verification results, commit SHAs.
