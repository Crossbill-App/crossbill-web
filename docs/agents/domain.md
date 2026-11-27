# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

This repo is **single-context**: one `GLOSSARY.md` and one `docs/adr/` at the root, covering `backend/`, `frontend/`, and `mcp-server/` together.

## Before exploring, read these

- **`GLOSSARY.md`** at the repo root — the ubiquitous language.
- **`docs/adr/`** — the ADRs that touch the area you're about to work in.

The architectural rules live in the root `CLAUDE.md`; treat it as authoritative where they overlap with anything here.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `GLOSSARY.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap. Record resolved terms and decisions with `/domain-modeling` (reached via `/grill-with-docs` and `/improve-codebase-architecture`), which updates `GLOSSARY.md` and adds ADRs.

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0001 (read models and query services) — but worth reopening because…_
