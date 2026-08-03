# ADR-0002: Semantic search over content embeddings

- **Status:** Proposed
- **Date:** 2026-08-02
- **Applies to:** `backend/`
- **Depends on:** ADR-0001 (read models and query services)

## Context

The app accumulates natural-language content across modules — notes
(`title` + `body`), highlights (`text`), and chapter digests
(`summary` + `keypoints`). The only cross-content retrieval today is
Postgres full-text search on highlights (`text_search_vector`, a `TSVECTOR`
in the `reading` module). That is lexical and single-type; it cannot answer
"what else in my library bears on this idea" across books, across content
kinds, or across languages.

We want semantic retrieval: nearest-neighbour search over dense embeddings, so
a Finnish reflection can surface a related English highlight, and a note can
rank against a digest on the same axis. The reading data is mixed
Finnish/English, and **there is no per-unit language field** — language lives
only on `book`. Model-per-language routing is therefore impossible; a single
multilingual model is the only coherent choice.

There is no existing embedding/vector code, no domain-events bus (use cases
enqueue background jobs explicitly), and a working async batch-job pipeline
(`JobBatch` + SAQ, the chapter-digest generation flow) that this feature reuses
wholesale.

## Decision

Introduce a **`semantic` context that lives only in `application/` and
`infrastructure/`** — no `domain/semantic/` module. An embedding row is derived
data: no invariants, no lifecycle, no aggregate. It is an asynchronously
maintained index plus its queries. Modelling it as a domain aggregate would add
a vacuous module and force the `domain-module-independence` contract to grow for
nothing.

### Model and providers

A **single multilingual model, `bge-m3` (1024-dim)**, on both environments:

- **dev:** local Ollama, `/v1/embeddings`
- **prod (Railway):** OpenRouter `baai/bge-m3`, `/api/v1/embeddings`
  (`$0.01`/M tokens, 8K context)

Both endpoints are OpenAI-compatible, so the client is one OpenAI-SDK caller
parameterised by base-URL + key + model — `EMBEDDING_PROVIDER` selects the
base-URL, nothing branches on provider in code. Using the *same* model in both
places means identical vectors and one fixed column dimension; dev and prod
remain separate data populations regardless.

New settings in `config.py`, parallel to and independent of the chat/digest
`AI_*` config (embeddings and generation will often want different providers):
`EMBEDDING_PROVIDER` (`ollama | openrouter | None`), `EMBEDDING_MODEL_NAME`,
`EMBEDDING_BASE_URL`, `EMBEDDING_MODEL_VERSION`, reusing the existing
`OPENROUTER_API_KEY`. The vector width is deliberately *not* a setting: it is
fixed by the column, so it lives in `infrastructure/semantic/dimensions.py` where
the ORM and the client's response validation both read it.

### Storage — one polymorphic table

The units are heterogeneous and span three modules, and the whole point is to
rank them against each other in one nearest-neighbour scan. So a single table
(pgvector via an Alembic `CREATE EXTENSION vector` migration), not a `vector`
column per source table:

```
embeddings(
  id,
  user_id,                 -- ownership filter for NN search
  content_type,            -- 'note' | 'highlight' | 'digest'
  content_id,              -- id within that type (no FK: polymorphic)
  note_id, highlight_id, digest_id,   -- cascade anchors, exactly one set
  book_id,                 -- FK -> books ON DELETE SET NULL (scope, not identity)
  embedding vector(1024),
  model_name, model_version,   -- idempotency spine
  content_hash,                -- idempotency spine
  created_at, updated_at,
  UNIQUE (content_type, content_id)
)
-- HNSW index on embedding (vector_cosine_ops); btree on user_id, book_id
```

**Deletion is the database's job, not the enqueuer's.** `content_type` +
`content_id` stays the logical key, but a polymorphic id cannot carry a
constraint, so nothing would prune an embedding whose note or digest was
deleted — and deletion often bypasses application code entirely
(`BookRepository.delete` issues one `DELETE` and lets `ON DELETE CASCADE` clear
the highlights, chapters and digests beneath it; no `enqueue_for` seam can fire).

Hence three nullable **cascade anchors**, `note_id` / `highlight_id` /
`digest_id`, each a real FK with `ON DELETE CASCADE`. Exactly one is set and it
always equals `content_id`, enforced by a `CHECK` so the duplication cannot
drift. Queries continue to use `content_type` + `content_id`; the anchors exist
only so the database can prune.

`book_id` is `ON DELETE SET NULL`, not `CASCADE`: it is a scoping hint, not
identity. A note can outlive the book it was linked to, so deleting that book
must clear the scope rather than drop a live note's embedding.

This leaves exactly one gap, and it is structural: **soft deletes**. Soft-deleting
a highlight is an `UPDATE` of `deleted_at`, so the row never leaves the table and
no foreign key can fire. `HighlightDeleteUseCase` therefore removes those
embeddings explicitly via `delete_for_many` — one statement per batch, not a job
each. That is why `reading` depends on two semantic ports rather than one: the
enqueuer for writes, the embedding repository for soft-delete cleanup.

The backfill sweep remains the backstop for every path.

This is infrastructure — the vector has no domain behaviour. It contrasts with
ADR-0001's "no projections, no separate read store": embeddings **are** a
derived, asynchronously-maintained projection. That is the deliberate exception
this ADR carves out, justified because the data cannot be computed inside a
request (it needs an external/inference call) and is pure index, never a source
of truth.

### Slice layout

| Where | What |
| --- | --- |
| `application/semantic/content_type.py` | `ContentType` enum, shared by all layers |
| `application/semantic/protocols/` | Ports: embedding client, embedding repository, content source |
| `application/semantic/services/embedding_enqueuer.py` | The one seam source modules call; no-ops when disabled |
| `application/semantic/commands/` | `GenerateContentEmbeddingUseCase` (task core), `EnqueueContentEmbeddingsUseCase` (backfill) |
| `application/semantic/queries/` | `SemanticSearchView` + query port; `SearchContentUseCase`, `RelatedContentUseCase` |
| `infrastructure/semantic/orm/` | `embeddings` table ORM |
| `infrastructure/semantic/repositories/` | Embedding repository (upsert / get_state / delete_for) |
| `infrastructure/semantic/clients/` | OpenAI-compatible embedding client (Ollama / OpenRouter by base-URL) |
| `infrastructure/semantic/content/` | Content source: `ContentType` → source ORM; text + hash; reconciliation query |
| `infrastructure/semantic/queries/` | Nearest-neighbour query adapter |
| `infrastructure/semantic/routers/` | `GET` search, `GET` related, `POST` backfill |

Cross-module coupling is concentrated in exactly two accepted places:

- **`content/content_source.py` reads other modules' ORM** to fetch embeddable
  text. Infra cross-module ORM reads are already sanctioned by ADR-0001.
- **Source-module commands depend on semantic ports**, application composing
  across modules — allowed. Write paths use `EmbeddingEnqueuer`: `notes` never
  imports embedding internals, it calls `enqueue_for("note", id)`.
  `HighlightDeleteUseCase` additionally depends on `EmbeddingRepository`, because
  a soft delete is the one case no foreign key can prune (see *Storage* below).

### The idempotency spine

Every write path ends in the same guard: **embed only if the row is missing or
stale**, where stale = `content_hash` mismatch OR `model_version` mismatch. This
single rule makes both live recalculation and backfill idempotent and makes the
three drift scenarios (flag toggled on after content existed, content edited
while off, model swapped) all resolve to one reconciliation query.

The reconciliation query outer-joins the stored state but evaluates staleness in
**Python, not SQL**: `content_hash` is a SHA-256 over text assembled in
application code, and there is no portable way to recompute it in both Postgres
and SQLite. Filtering on model identity alone in SQL would miss content drift
entirely — the case where a job exhausted its retries is exactly the one backfill
exists to catch.

`GenerateContentEmbeddingUseCase` (the task core):

1. `content_source.get_embeddable(type, id)` → text + hash + `book_id`, or
   `None` if the source was deleted → `repository.delete_for(type, id)`, done.
2. Compare hash + `model_version` against `repository.get_state(type, id)`;
   equal → skip (no model call).
3. Else `client.embed([text])` → upsert.

Embeddable text per type: note = `title` + `body`; highlight = `text`;
digest = `summary` + `keypoints`. Because `content_hash` covers exactly this
text, edits that do not change it never re-embed — note re-tagging
(`update_content` untouched) and digest answer edits (`summary`/`keypoints`
untouched) are silently no-ops.

### Ingestion — reuse the `JobBatch` pipeline

Add `CONTENT_EMBEDDING` to `JobBatchType`; the `JobBatch` entity, ORM,
atomic-increment progress, and `after_process` hook are type-agnostic and need
no changes. Add `generate_content_embedding(ctx, *, batch_id=None, content_type,
content_id, user_id)` to `worker.py` with a `_build_embedding_handler(db)` (the
worker wires DI by hand), registered in both worker-settings function lists.

Enqueue paths (all via `EmbeddingEnqueuer`, which no-ops when
`embeddings_enabled` is false):

- **Note create/update** — `enqueue_for(NOTE, id)`, a single job (no batch).
- **Highlight KOReader upload** — after `bulk_save(unique)`,
  `enqueue_many(HIGHLIGHT, saved_ids, book)` as a batch. The upload path already
  dedups via `content_hash` before saving, so re-syncs enqueue only genuinely
  new highlights.
- **Digest generation** — `enqueue_for(DIGEST, id)` after `digest_repo.save`.
- **Backfill** — `EnqueueContentEmbeddingsUseCase` runs the reconciliation query
  (missing OR stale, optionally scoped to a book), creates a `JobBatch`, and
  enqueues one job per work item. Triggered manually via `POST`; it gates
  nothing — it is catch-up for old content and post-model-swap re-embeds. Batch
  progress is visible for free through the existing batch views.

  Work items also include **orphans** — embeddings whose source row is gone or
  soft-deleted. They need no special delete path: the job's `get_embeddable`
  returns `None` and the spine's "source missing → `delete_for`" branch prunes
  the row. Deleting content therefore does not enqueue anything; the index is
  reconciled on the next backfill.

### Read side

Both are `queries/` read use cases (ADR-0001: routers call use cases, reads
included).

- **`SearchContentUseCase(query_text, user_id, filters)`** — `client.embed` the
  query, then `semantic_search_query.nearest(vector, user_id, filters, k)`.
- **`RelatedContentUseCase(content_type, content_id)`** — reads the already
  indexed vector for that unit (no embedding call), NN search excluding self.

The NN adapter is user-scoped (`WHERE user_id = :u`). It does **not** join the
source tables to filter soft-deleted content: the index stores no source state,
and joining three modules' tables into the ranking query would put cross-module
knowledge in the adapter. Instead, deleted units are dropped during hydration —
which means ranking exactly `k` rows would silently return fewer than `k`. So the
read use cases over-fetch (`overfetch_limit`) and trim to `k` after hydrating.
That is a mitigation, not a guarantee; keeping the index clean is backfill's job.

Result rows carry `(content_type, content_id, book_id, score)`; the read use case
hydrates display fields through the content source, batched by content type — at
most three queries per page regardless of `k`, selecting only the columns
hydration reads rather than whole ORM entities (which would drag in
selectin-loaded relationships). The earlier per-hit N+1 this ADR accepted at
launch `k` is gone.

Query adapters obey ADR-0001 Rule 1 (queries never decide): they select, join,
filter, order — no business rules in SQL.

### Feature gate — one flag, ingestion only

`embeddings_enabled = EMBEDDING_PROVIDER is not None` in `feature_flags.py`
(mirroring `ai_enabled`), plus a `require_embeddings_enabled` dependency
mirroring `require_ai_enabled`. **No separate exposure/visibility flag:** partial
coverage is acceptable — an un-embedded unit simply does not appear in results.
Ingestion runs whenever a provider is configured.

### Contracts

- `domain-module-independence`: **unchanged** — there is no `domain/semantic/`.
- `queries-are-dead-ends`: `SemanticSearchView` is a read DTO; the
  wildcard-covered contract already forbids `domain` and `*.commands` from
  importing `*.queries`, so `semantic` is covered without edits.

## Alternatives considered

- **A `vector` column on each source table.** Rejected: cross-content ranking
  would need UNION-ing three indexes and could never rank a note against a
  highlight on one axis — the core use case.
- **A `domain/semantic/` module with an `Embedding` aggregate.** Rejected: no
  invariants or lifecycle to protect; it would be a module wrapping an enum and
  a value object, and would grow the independence contract for nothing.
- **Provider-branching client like `ai_model.py`.** Unnecessary: Ollama and
  OpenRouter both expose OpenAI-compatible `/embeddings`, so provider is just a
  base-URL.
- **Different models per environment** (e.g. local `bge-m3`, prod
  `text-embedding-3-large`). Rejected: mismatched dimensions would need two
  column definitions / migrations. Same model both sides = one 1024-dim column.
- **Embedding the query synchronously inside the write request** for live
  recalc. Rejected: adds an external call and a failure mode to note/digest
  saves; the batch pipeline already models retries and progress.
- **Emitting domain events on save, handled into jobs.** Rejected for now: no
  event bus exists; source commands enqueue explicitly, matching the digest
  flow. If a bus is later added, the `enqueue_for` calls move to handlers.

## Explicitly NOT adopted

- **Chunking / document-splitting.** All units are short (notes, highlights,
  digest summaries) and fit `bge-m3`'s 8K context — one vector per unit.
- **A visibility feature flag / coverage gating.** Partial coverage is fine.
- **Hybrid lexical+semantic ranking.** The existing highlight FTS
  (`plainto_tsquery`) stays as-is and complementary; fusing the two is possible
  later but out of scope.
- **Reading-session `ai_summary` as an embeddable unit.** Deferred; it is
  request-time, written once. Adding it later is one more `ContentType`.
- **Re-embedding on model swaps to a different dimension.** That is a column
  migration + full backfill by construction; same-dimension swaps are a
  `model_version` bump + reconciliation.

## Consequences

**Good**

- One index, one HNSW scan answers cross-content, cross-book, cross-language
  retrieval — the feature that motivates the work.
- The idempotency spine collapses live recalc, backfill, toggling, and model
  drift into a single "missing or stale" rule.
- Reuses the `JobBatch` pipeline wholesale — progress tracking is free.
- Ships behind ingestion-only gating; read features can land incrementally on a
  partially-populated index.
- Hexagonal boundaries hold with no new domain module and no contract changes.

**Costs**

- A derived projection maintained outside the write transaction — the exception
  to ADR-0001's "no projections". It can drift between a save and its job
  running; the reconciliation query is the backstop.
- Cross-module ORM reads in `content_source`, and source-module commands
  carrying one embedding dependency each — accepted coupling, concentrated.
- Result hydration costs up to three extra queries per page (one per content
  type present), and fetches text for every over-fetched candidate rather than
  only those that survive the cap. Revisit with a denormalised excerpt column if
  result sets grow far beyond launch `k`.
- pgvector is new operational surface (extension, HNSW build/maintenance).

## Open questions

- Denormalise a `content_excerpt` onto `embeddings` for zero-join result
  rendering, accepting display-only staleness? (Deferred; batched hydration is
  cheap enough at launch `k`.)
- Backfill scope granularity: whole-library vs per-book `POST` — start per-book
  to bound batch size?
- Filtered HNSW recall under `WHERE user_id` at larger corpora — measure before
  it matters.
