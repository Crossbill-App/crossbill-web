# ADR-0002: Semantic search over content embeddings

- **Status:** Accepted
- **Date:** 2026-08-03
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

## Consistency model

**This section is the load-bearing one.** An embeddings table is a copy of text
that lives in other modules, and every hard question in this design — foreign
keys, orphans, what the read path filters, which modules end up coupled —
follows from one decision: *how exact is the copy required to be?* Answering it
first is what keeps the rest of the design from being discovered a piece at a
time.

1. **The index is a derived artifact, never a source of truth.** It is
   reconciled by backfill. Nothing outside the semantic slice is obliged to keep
   it exact, and no user-facing operation may fail because it is stale.
2. **The read path is authoritative.** Every hit is resolved through its source
   module during hydration, and a hit whose source cannot be resolved is
   dropped. Deleted content therefore cannot surface *regardless of index
   state*. This is a local guarantee, not one contingent on a foreign key having
   fired or a cleanup having succeeded — and it is free, because the source text
   must be fetched to render a result anyway.
3. **Hard deletes are the database's job.** Deletion frequently bypasses
   application code entirely: `BookRepository.delete` issues one `DELETE` and
   lets `ON DELETE CASCADE` clear the highlights, chapters and digests beneath
   it, so no application seam can fire. Typed FK cascade anchors are what prune
   the index (see *Storage*).
4. **Soft deletes are reconciled by the backfill orphan sweep.** A soft delete
   is an `UPDATE` of `deleted_at`; the row never leaves the table and no foreign
   key can see it. Rule 2 means such an embedding is invisible in the meantime,
   so the sweep is sufficient and nothing has to happen at the delete site.

Consequence worth stating plainly, because it is what keeps this PR small:
**no existing domain module is touched.** The only cross-module contact is
`infrastructure/semantic/content/content_source.py` reading other modules' ORM,
which ADR-0001 already sanctions. Explicit cleanup at delete sites — the thing
that would make a source module depend on a semantic port — is deliberately
deferred (see *Deferred*).

## Decision

Introduce a **`semantic` context that lives only in `application/` and
`infrastructure/`** — no `domain/semantic/` module. An embedding row is derived
data: no invariants, no lifecycle, no aggregate. It is an asynchronously
maintained index plus its queries. Modelling it as a domain aggregate would add
a vacuous module and force the `domain-module-independence` contract to grow for
nothing.

This is infrastructure — the vector has no domain behaviour. It contrasts with
ADR-0001's "no projections, no separate read store": embeddings **are** a
derived, asynchronously-maintained projection. That is the deliberate exception
this ADR carves out, justified because the data cannot be computed inside a
request (it needs an external inference call) and is pure index, never a source
of truth.

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
  user_id,                 -- FK -> users ON DELETE CASCADE; ownership filter for NN search
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
-- HNSW index on embedding (vector_cosine_ops); btree on user_id, book_id;
-- partial btree on each anchor WHERE <anchor> IS NOT NULL
```

`content_type` + `content_id` is the logical key, but a polymorphic id cannot
carry a constraint, so nothing would prune an embedding whose note or digest was
deleted. Hence three nullable **cascade anchors**, `note_id` / `highlight_id` /
`digest_id`, each a real FK with `ON DELETE CASCADE`. Exactly one is set and it
always equals `content_id`, enforced by a `CHECK`. Queries continue to use
`content_type` + `content_id`; the anchors exist only so the database can prune.

The `CHECK` tests each anchor for `IS NOT NULL` *before* comparing it to
`content_id`, and that is not decoration. Comparing a NULL anchor to
`content_id` yields NULL, the whole disjunction yields NULL, and SQL treats any
`CHECK` that is not false as satisfied — so the naive form admits precisely the
row the anchors exist to forbid: one that no foreign key can cascade and that
the orphan sweep, which reads the anchor, cannot see either.

`book_id` is `ON DELETE SET NULL`, not `CASCADE`: it is a scoping hint, not
identity. A note can outlive the book it was linked to, so deleting that book
must clear the scope rather than drop a live note's embedding. Content that
genuinely dies with the book is cascaded by the typed anchors instead.

The anchor indexes are **partial** (`WHERE <anchor> IS NOT NULL`), because each
is set only on rows of its own content type. The ORM declares them in
`__table_args__` with the same `postgresql_where`, rather than `index=True` on
the columns — plain `index=True` builds a same-named non-partial index, which
makes `alembic revision --autogenerate` report a diff forever and gives
`create_all` (tests, dev databases) a different shape than production.

### Slice layout

| Where | What |
| --- | --- |
| `application/semantic/content_type.py` | `ContentType` enum, shared by all layers |
| `application/semantic/idempotency.py` | The staleness rule, defined once |
| `application/semantic/protocols/` | Ports: embedding client, embedding repository, content source |
| `application/semantic/commands/` | `GenerateContentEmbeddingUseCase` (task core), `EnqueueContentEmbeddingsUseCase` (backfill) |
| `application/semantic/queries/` | `SemanticSearchView` + query port; `SearchContentUseCase`, `RelatedContentUseCase` |
| `infrastructure/semantic/orm/` | `embeddings` table ORM |
| `infrastructure/semantic/repositories/` | Embedding repository (upsert / get_state / delete_for) |
| `infrastructure/semantic/clients/` | OpenAI-compatible embedding client (Ollama / OpenRouter by base-URL) |
| `infrastructure/semantic/content/` | Content source: `ContentType` → source ORM; text + hash; reconciliation query |
| `infrastructure/semantic/queries/` | Nearest-neighbour query adapter |
| `infrastructure/semantic/routers/` | `GET` search, `GET` related, `POST` backfill |

Cross-module coupling is concentrated in exactly one accepted place:
**`content/content_source.py` reads other modules' ORM** to fetch embeddable
text. Infra cross-module ORM reads are already sanctioned by ADR-0001.

### The idempotency spine

Every write path ends in the same guard: **embed only if the row is missing or
stale**, where stale = `content_hash` mismatch OR `model_name`/`model_version`
mismatch. This single rule makes both live recalculation and backfill idempotent
and makes the three drift scenarios (flag toggled on after content existed,
content edited while off, model swapped) all resolve to one reconciliation query.

**The rule lives in exactly one module**, `application/semantic/idempotency.py`,
and both callers import it: the backfill's reconciliation filter and the job's
re-check. Both *call sites* are correct and stay —
backfill-filters-then-job-rechecks is a deliberate TOCTOU guard, since content
can change between the two and a model call is what is at stake. It is the
*rule* that must exist once. Writing it twice is not hypothetical: an earlier
implementation compared `model_name` raw while storing it coerced with `or ""`,
so with the setting unset every row read as permanently stale and re-embedded on
every job run.

The reconciliation query outer-joins the stored state but evaluates staleness in
**Python, not SQL**: `content_hash` is a SHA-256 over text assembled in
application code, and there is no portable way to recompute it in both Postgres
and SQLite. Filtering on model identity alone in SQL would miss content drift
entirely — the case where a job exhausted its retries is exactly the one backfill
exists to catch.

`GenerateContentEmbeddingUseCase` (the task core):

1. `content_source.get_embeddable(type, id)` → text + hash + `book_id`, or
   `None` if the source is gone → `repository.delete_for(type, [id])`, done.
2. `is_current(state, hash, settings)` against `repository.get_state(type, id)`;
   current → skip (no model call).
3. Else `client.embed([text])` → upsert.

Embeddable text per type: note = `title` + `body`; highlight = `text`;
digest = `summary` + `keypoints`. Because `content_hash` covers exactly this
text, edits that do not change it never re-embed — note re-tagging
(`update_content` untouched) and digest answer edits (`summary`/`keypoints`
untouched) are silently no-ops.

Staleness deliberately does **not** compare scope (`book_id`): a note whose book
links changed with its text untouched would keep a stale scope. That is
unreachable today only because `UpdateNoteUseCase` passes the note's existing
`book_ids` straight through, and the staleness check says so, so the assumption
is visible when book links become editable.

### Ingestion — reuse the `JobBatch` pipeline

Add `CONTENT_EMBEDDING` to `JobBatchType`; the `JobBatch` entity, ORM,
atomic-increment progress, and `after_process` hook are type-agnostic and need
no changes. Add `generate_content_embeddings(ctx, *, batch_id, content_type,
content_ids, user_id)` to `worker.py` with a `_build_embedding_handler(db)` (the
worker wires DI by hand), registered in both worker-settings function lists.

**Backfill is the only ingestion trigger in this ADR's scope.**
`EnqueueContentEmbeddingsUseCase` runs the reconciliation query (missing or
stale, optionally scoped to a book), creates a `JobBatch`, and enqueues one job
per **slice** of work items. Triggered manually via `POST`; it gates nothing — it
is catch-up for existing content and post-model-swap re-embeds. Batch progress is
visible for free through the existing batch views. Live enqueue-on-write is
deferred (see *Deferred*), so until it lands the index is populated by running a
backfill.

A job takes a slice of ids of one content type (32) rather than a single id.
One job per unit made the unit of work match the unit of failure, which is
tidy, but it also made it the unit of *cost*: one queue round trip per unit
inside the request, and one provider request per unit in the worker, when the
embeddings API accepts many inputs per call. A slice amortises both by the
slice size. It is deliberately below the client's own per-request cap (96,
OpenRouter's limit, which the client chunks at independently): the number that
matters is how much text a local Ollama GPU is asked to hold at once, not the
provider's ceiling.

`total_jobs` counts slices, so batch progress is per slice. The cost is blast
radius — a slice fails as a unit, so one unit whose text the provider rejects
takes its slice down with it on every retry. Accepted for now, since no such
unit exists yet: the fallback (embed one at a time on the error path) is noted
as a `TODO` at the call site, and the task handler logs the slice's ids on
failure so the offender is identifiable without a code change. Note that
staleness is still decided per unit, not per slice — a slice re-embeds only its
stale members, or one drifted note would pay to re-embed 31 current ones.

What this does **not** fix is the reconciliation scan that feeds it, which still
loads every candidate unit's text into the request to hash it. Tracked
separately in issue #534.

Work items also include **orphans** — embeddings a soft-deleted highlight left
behind. They need no special delete path: the job's `get_embeddable` returns
`None` and the spine's "source missing → `delete_for`" branch prunes the row.
Only highlights can strand an embedding: notes and digests are hard-deleted
only, and their typed FK anchors cascade the row away in either race ordering
(the FK check takes `FOR KEY SHARE` on the referenced row, so a concurrent
`DELETE` either waits for the insert and then cascades it, or wins and the
insert fails on the FK, leaving the retry to resolve `None`). Sweeping for notes
and digests would be an unindexed anti-join hunting rows that cannot exist, so
the sweep is a positive lookup on `highlight_id` alone.

When an enqueue fails partway, the loop stops and **the units it never reached
are recorded as failures** rather than trimmed out of `total_jobs`. Trimming
made a backfill of 500 units that broke at item 3 terminate as "completed,
total_jobs=3", with nothing to say the other 497 were dropped.

Two backfills can **overlap**, and nothing dedups the jobs they enqueue.
Refusing a new batch while one is active was considered and rejected: the
enqueue loop runs inside the HTTP request, so a request that dies partway leaves
a batch that never reaches a terminal status, and gating on "a batch is active"
would then lock the user out of backfill permanently. Wasted work is the better
failure of the two — most duplicates lose the hash race and cost nothing. The
fix belongs at the queue instead, as deterministic job keys, so that
re-enqueueing a unit collapses into the pending job rather than being gated.
Tracked in issue #531.

### Read side

Both are `queries/` read use cases (ADR-0001: routers call use cases, reads
included).

- **`SearchContentUseCase(query_text, user_id, filters)`** — `client.embed` the
  query, then `semantic_search_query.nearest(vector, user_id, filters, k)`.
- **`RelatedContentUseCase(content_type, content_id)`** — reads the already
  indexed vector for that unit (no embedding call), NN search excluding self.

The NN adapter is user-scoped (`WHERE user_id = :u`). It does **not** join the
source tables to filter deleted content: the index stores no source state, and
joining three modules' tables into the ranking query would put cross-module
knowledge in the adapter. It does not need to — consistency-model rule 2 puts
that guarantee in hydration, where it is free.

There is deliberately **no over-fetch**. Hydration drops are rare, batched
hydration resolves every candidate up front (so a cushion would pay for itself
on every search to defend against something that should not happen), and a page
short by one in a rare race is harmless — there is no pagination cursor to
desynchronise.

Result rows carry `(content_type, content_id, book_id, score)`; the read use case
hydrates display fields through the content source, batched by content type — at
most three queries per page regardless of `k`, selecting only the columns
hydration reads rather than whole ORM entities (which would drag in
selectin-loaded relationships).

Two pgvector operational details the SQLite fallback cannot exercise, so they are
recorded here rather than discovered in production.

The first is **filtered recall**. The HNSW index is global over `embedding` while
every query filters `user_id` *after* the scan, so a single-pass scan hands back
its `hnsw.ef_search` candidates, the filter discards the ones belonging to other
users, and the query answers with the remainder — nothing at all when another
user's rows sit between the query vector and this user's. That is a total recall
failure, not a degradation, and it gets likelier as the index grows. Each query
therefore sets `hnsw.iterative_scan = strict_order` (pgvector 0.8+), which
resumes the scan until the limit is met, transaction-scoped. Measured against
0.8.6 on a 10k-row index with the searching user's rows behind that noise: 0 rows
returned without it, the full 10 with it. `strict_order` over `relaxed_order`
because relaxed returns rows slightly out of distance order and the adapter's
`ORDER BY distance, id` would not repair it — the planner takes the index's
ordering as given for the leading key.

`ef_search` is still set (four candidates per requested row, since the default 40
is below the 50 the router allows), but it is now a first-pass seed rather than
the thing recall depends on. What the iterative scan does *not* fix is
`hnsw.max_scan_tuples`, default 20 000, which bounds the resumed scan: a user
whose rows sit behind more than that many of other users' is short-changed again.
This corpus is nowhere near that, and raising it is a one-line change when it is.

The second is ordering: `ORDER BY distance` alone is non-deterministic, so both
adapters break ties on the embedding id.

Query adapters obey ADR-0001 Rule 1 (queries never decide): they select, join,
filter, order — no business rules in SQL.

### Feature gate — one flag, one pattern

`embeddings_enabled = EMBEDDING_PROVIDER is not None` in `feature_flags.py`
(mirroring `ai_enabled`), plus a `require_embeddings_enabled` **decorator**
mirroring `require_ai_enabled`. **No separate exposure/visibility flag:** partial
coverage is acceptable — an un-embedded unit simply does not appear in results.

Matching the existing decorator requires the embedding client to be built
**lazily**, and that is the whole reason `LazyEmbeddingClient` exists. A
decorator's body runs *after* FastAPI has resolved the endpoint's parameter
dependencies, so if the DI container builds a client that raises on missing
configuration, a disabled feature answers 500 before the gate ever runs. The AI
code has exactly the same raising behaviour — `_get_model()` raises when no
provider matches — and avoids the problem purely by constructing inside the
handler, which is what `get_ai_model`'s cache docstring describes. So the
container registers a client that defers `build_embedding_client` until the first
`embed()`. The worker keeps building eagerly: it only runs when a job exists, and
there a loud failure at construction is what you want.

The gate answers **403**. `require_ai_enabled` answers 410 Gone, which means
"existed here, permanently removed" rather than "not configured on this server";
aligning the AI endpoints is a small follow-up, not a reason to propagate it.

### Contracts

- `domain-module-independence`: **unchanged** — there is no `domain/semantic/`.
- `queries-are-dead-ends`: `SemanticSearchView` is a read DTO; the
  wildcard-covered contract already forbids `domain` and `*.commands` from
  importing `*.queries`, so `semantic` is covered without edits.
- `orm-boundary`: unchanged — `infrastructure.semantic.content` is not among the
  contract's `source_modules`, which is what permits its cross-module ORM reads.

## Deferred

Sequenced deliberately, so each lands as its own reviewable change:

- **Live enqueue-on-write.** An `EmbeddingEnqueuer` application service called
  from note create/update, highlight upload and digest generation, so new and
  edited content is embedded without a manual backfill. It no-ops when the flag
  is off and swallows enqueue failures — a missed embedding must never fail a
  user's write. This is the first thing that makes a source module depend on a
  semantic port.
- **Explicit soft-delete cleanup.** Removing a soft-deleted highlight's
  embedding at the delete site rather than waiting for the sweep. This is worth
  care disproportionate to its size: the ids in a delete request are unverified
  caller input, so the cleanup must be driven by the ids the repository
  *actually* deleted, not the ids that were asked for — otherwise one user can
  prune another's embeddings.
- **Deterministic job keys** so overlapping backfills collapse (issue #531).
- **Frontend.** Surfacing search and related content in the UI.
- **Production wiring.** OpenRouter `baai/bge-m3`, confirming pgvector on
  Railway — **0.8 or newer**, since the read path sets `hnsw.iterative_scan` —
  and running the migration there.

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
- **Embedding synchronously inside the write request.** Rejected: adds an
  external call and a failure mode to note/digest saves; the batch pipeline
  already models retries and progress.
- **Emitting domain events on save, handled into jobs.** Rejected for now: no
  event bus exists; source commands will enqueue explicitly, matching the digest
  flow. If a bus is later added, the `enqueue_for` calls move to handlers.
- **Joining source tables into the ranking query** to filter deleted content.
  Rejected: it puts three modules' knowledge into the adapter to buy something
  hydration already guarantees for free.

## Explicitly NOT adopted

- **Chunking / document-splitting.** Units are short in practice (notes,
  highlights, digest summaries) — one vector per unit. "In practice" is not a
  guarantee, though: `notes.body` is an unbounded `Text` column with no length
  validation on the way in, so `ContentSource` truncates at a character budget
  (`MAX_EMBEDDABLE_CHARS`) rather than trusting the assumption. Both the
  reconciliation scan and `get_embeddable_many` truncate through the same
  helpers, because they hash independently and a unit whose two hashes disagree
  is stale on every pass. The tail of an over-long unit is not indexed; indexing
  it is what chunking would buy, and that is the thing not being adopted here.
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
- The idempotency spine collapses backfill, toggling, and model drift into a
  single "missing or stale" rule, defined in one place.
- Reuses the `JobBatch` pipeline wholesale — progress tracking is free.
- Hexagonal boundaries hold with no new domain module, no contract changes, and
  no edit to any existing module.

**Costs**

- A derived projection maintained outside the write transaction — the exception
  to ADR-0001's "no projections". It drifts between a content change and the next
  backfill; the read path is what keeps that invisible.
- Until live enqueue lands, new content is not searchable until a backfill runs.
  That is the price of shipping the slice on its own, and it is recoverable at
  any time by pressing the button.
- Cross-module ORM reads in `content_source` — accepted coupling, concentrated
  in one file.
- Result hydration costs up to three extra queries per page (one per content
  type present). Revisit with a denormalised excerpt column if result sets grow
  far beyond launch `k`.
- pgvector is new operational surface (extension, HNSW build/maintenance), and
  the parts that only exist on Postgres — the vector operators, HNSW, `ef_search`
  — cannot be covered by the SQLite test suite.

## Open questions

- Denormalise a `content_excerpt` onto `embeddings` for zero-join result
  rendering, accepting display-only staleness? (Deferred; batched hydration is
  cheap enough at launch `k`.)
- Backfill scope granularity: whole-library vs per-book `POST` — start per-book
  to bound batch size?
- Filtered HNSW recall under `WHERE user_id` is handled by 0.8's iterative scan,
  but only as far as `hnsw.max_scan_tuples` (20 000) reaches. Raise it, or
  partition the index by user, if a single user's rows ever sit behind that many
  of another's?
