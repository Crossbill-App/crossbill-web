---
name: ddd-migration
description: Step-by-step checklist for migrating a backend service to the DDD/hexagonal architecture. Use when porting an existing service, repository, or router to domain entities and repository protocols.
---

# DDD Migration Checklist

The architectural rules themselves live in the root `CLAUDE.md` and always apply. This
checklist is the *procedure* for porting an existing service onto them.

1. ✓ Read the migration plan document if one exists
2. ✓ Create domain entities/value objects in domain layer (no ORM dependencies)
3. ✓ Create/update repository in infrastructure layer (all ORM code here only)
4. ✓ Convert application service to work with domain entities, not ORM models
5. ✓ After ANY file deletion/move, grep for old import paths and update them
6. ✓ Ensure value objects are converted to primitives before Pydantic schemas
7. ✓ For SQLAlchemy joinedload collections, use `.unique()`
8. ✓ Run pyright and fix all type errors
9. ✓ Run `uv run lint-imports` — the post-edit hook does not run it
10. ✓ Run pytest and fix all test failures
11. ✓ Do NOT declare complete until all checks pass
