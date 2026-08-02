# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

This repo is **single-context**: one `CONTEXT.md` and one `docs/adr/` at the root, covering `backend/`, `frontend/`, and `mcp-server/` together.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root, and
- **`docs/adr/`** — read ADRs that touch the area you're about to work in.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

`CLAUDE.md` at the root carries the architectural rules (DDD layer boundaries, type checking, testing) — read it too, and treat it as authoritative where it overlaps with anything here.

## File structure

```
/
├── CLAUDE.md              ← architectural rules, tooling, conventions
├── CONTEXT.md             ← glossary / ubiquitous language (created lazily)
├── docs/
│   ├── adr/               ← architecture decision records (created lazily)
│   └── agents/            ← this file, issue-tracker.md, triage-labels.md
├── backend/src/
├── frontend/src/
└── mcp-server/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders) — but worth reopening because…_
