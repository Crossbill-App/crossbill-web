---
name: ddd-migration
description: Step-by-step checklist for migrating a backend service to the DDD/hexagonal architecture. Use when porting an existing service, repository, or router to domain entities and repository protocols.
---

# DDD Migration Checklist

The architectural rules live in the root `CLAUDE.md` and always apply; this is
the porting order.

1. Read the migration plan document if one exists
2. Create domain entities/value objects in the domain layer
3. Create/update the repository in the infrastructure layer (all ORM code moves here)
4. Convert the application service to work with domain entities
5. After any file deletion or move, grep for the old import paths and update them
6. Verify before declaring done: `pyright`, `uv run lint-imports`, and the full
   `pytest` suite — all clean
