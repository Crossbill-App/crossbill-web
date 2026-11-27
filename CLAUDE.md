# Crossbill

Self-hosted reading companion: it collects what a reader marked on their
e-reader and helps them work it into understanding. `backend/` is FastAPI on a
DDD/hexagonal architecture, `frontend/` is React + MUI, `mcp-server/` exposes
the API to MCP clients, and `site/` is the Astro docs site. The KOReader plugin
is a client of the backend. `backend/CLAUDE.md`, `frontend/CLAUDE.md` and
`site/AGENTS.md` load when you work in those directories.

## Cross-cutting rules

- **API changes regenerate the client.** After changing a backend endpoint,
  run `make api-client` (no running backend needed) and commit
  `backend/openapi.json` with the regenerated frontend client; CI fails if
  either is stale.
- **The plugin-only surface is version-gated.** `/ereader/*`,
  `/highlights/sync` and `/reading_sessions/sync` — the last two still
  reachable under their deprecated `/upload` aliases — are called by the
  KOReader plugin alone, and reject clients older than the minimum in
  `backend/src/infrastructure/common/client_version.py` with HTTP 426. A change
  that breaks their request or response contract for old plugins bumps the
  `koreader-plugin` minimum in the same PR.

## Duplication (jscpd)

CI fails once duplicated lines pass the `threshold` in `backend/.jscpd.json` or
`frontend/.jscpd.json`, and a Stop hook flags clones overlapping lines the turn
changed. The threshold is a **ratchet**: when a refactor drops the percentage,
lower it in the same commit; when the check fails, extract the shared code.
Narrow a scan to one area with
`cd backend && npx jscpd --no-tips --reporters console src/application/notes`.

## Working style

- Keep to the task: redesign the architecture or draft broader plans only when
  asked.
- On bigger tasks, make small, logically separated commits.

## Agent docs

- **Domain language and decisions**: before naming a domain concept or working
  in an area an ADR covers, read `docs/agents/domain.md` (glossary in
  `GLOSSARY.md`, ADRs in `docs/adr/`).
- **Issue tracker**: GitHub issues in `Crossbill-App/crossbill-web`, tracked on
  the project board — `docs/agents/issue-tracker.md`.
- **Triage labels**: the five canonical roles use their default label strings —
  `docs/agents/triage-labels.md`.
