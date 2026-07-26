# Read models (query services)

How to port a view off the repositories and onto a query service. The decision
and its rationale live in
[`docs/adr/0001-read-models-and-query-services.md`](../adr/0001-read-models-and-query-services.md);
this file is the recipe.

The reference implementation is the book-details view:

| File | Role |
| --- | --- |
| `backend/src/application/library/queries/book_details.py` | View DTOs + `BookDetailsQueryProtocol` (the port) |
| `backend/src/application/library/queries/get_book_details_use_case.py` | Read use case the router calls |
| `backend/src/infrastructure/library/queries/book_details_query.py` | Adapter: ORM rows → view DTOs |
| `backend/src/infrastructure/library/routers/books.py` | Router + view-DTO → Pydantic mapping |
| `backend/tests/unit/infrastructure/library/queries/test_book_details_query.py` | Adapter tests |

The `jobs` module is a smaller second example: one view DTO, one port with two
query methods, no cross-module joins
(`backend/src/infrastructure/jobs/queries/job_batch_query.py`). The `notes`
module shows the same one-DTO-two-methods shape over many-to-many links
(`backend/src/infrastructure/notes/queries/note_query.py`). The `learning`
module's book-flashcards view is the smallest full port that still reuses a
domain-owned rule — two selects plus `LabelResolutionService`
(`backend/src/infrastructure/learning/queries/book_flashcard_query.py`). The
`library` module's book lists are the paginated example, and the one where the
port emptied the repository of everything but aggregate lifecycle
(`backend/src/infrastructure/library/queries/book_list_query.py`). In the
`reading` module, the highlight search is the view ADR-0001 opens with and the
port that finally deleted `HighlightRepositoryProtocol.search`
(`backend/src/infrastructure/reading/queries/highlight_search_query.py`), and
the session list is the one whose data does not all live in Postgres
(`backend/src/infrastructure/reading/queries/reading_session_query.py`).

## Does this view qualify?

Port a view when you see any of:

- A repository method that returns tuples of unrelated entities
  (`list[tuple[Highlight, Book, Chapter | None, list[Tag], list[Flashcard]]]`).
  A tuple like that is a view row, not an aggregate.
- A use case that calls three or more repositories and stitches the results
  together for one response.
- An aggregate loaded in full so that one or two of its fields can be rendered,
  or loaded and then partly discarded.
- A `limit=10000`-style call standing in for "all of them".

Do **not** fully port:

- Endpoints that read in order to write. Those are commands; they need
  aggregates and their invariants.
- Single-entity GETs already served by one `find_by_id` and one mapper. The
  ceremony would exceed the benefit.

"Reads in order to write" means the use case itself mutates the data the view is
about. A row written *by a collaborator* as a side effect does not make the read
a command: the flashcard-suggestion endpoints persist an `AIUsageRecord` inside
`AIService`, and they are still reads. The ADR settles the general case in the
other direction too — a read use case may call a command outright, which is how
`GetBookDetailsUseCase` stamps `last_viewed`.

When a view sits on the line, ask what the port would remove. A read whose
repository finder has no other caller takes that finder with it, and the write
side gets smaller — `find_by_reference` died with the active-batch view, which
the halfway option could never have achieved. A read that shares `find_by_id`
with a command removes nothing, so stay minimal there.

That question breaks ties; it does not overrule the bullets above. A view that
already trips one of them qualifies however widely its finders are shared —
the ereader prereading list calls nothing but finders that commands also use,
and porting it still deleted a Book aggregate load, every Chapter aggregate of
the book, and a hand-rolled DTO that was a view DTO in all but location. Ask
what the port removes only when nothing on the list applies.

A simple read that doesn't qualify still **belongs in** `queries/` — a read
never sits in `commands/`, whatever its internals. Apply the ADR's halfway
option at its most minimal: the read use case delegates to the existing
repository and returns domain entities. No adapter, no invented DTOs, no query
port. The package placement (and the dead-ends contract that keys off it) is
the point; the internals can be tightened later if the view ever grows.
`GetTagsForBookUseCase` (`application/tagging/queries/`) is the reference for
this shape.

Not every read serves a view. `GetUserByIdUseCase`
(`application/identity/queries/`) backs the `get_current_user` FastAPI
dependency: no endpoint of its own, and its `User` reaches every router in the
app, which then passes it into commands. For a read like that the halfway
option is not the economical choice, it is the only legal one — handing back a
view DTO would put a read model on the input side of a command, which Rule 2
forbids. **A read whose result flows into a command keeps returning the domain
entity.** Put it in `queries/` and stop there.

## The layout

```
src/application/<module>/queries/      view DTOs, query protocol, read use cases
src/application/<module>/commands/     COMMANDS ONLY
src/infrastructure/<module>/queries/   the adapter (may import ORM models)
```

A view's query belongs to the module that owns the view. The adapter may import
any module's `orm` package for joins — infrastructure is one layer.

Naming note: classes keep the `*UseCase` suffix on both sides ("use case"
names the layer role; the package names the kind). `commands/` was called
`use_cases/` before ADR-0001; every module has since been renamed, so a
`use_cases/` package in a diff is a mistake, not a leftover.

A helper that both sides need (`notes`' `parse_note_kind`, which turns the
API's kind string into a `NoteKind`) stays where it is and is imported by the
query. The dead-ends contract is one-directional — `commands` must not import
`queries`, not the reverse — so this is allowed, and it beats duplicating the
conversion or inventing a third package to hold one function.

## Recipe

### 1. Define the DTOs and the port

In `src/application/<module>/queries/<view_name>.py`:

- `@dataclass(frozen=True)` per view shape. Use primitives and simple value
  types (`int`, `str`, `datetime`, `Position`, a `StrEnum`) — never domain
  entities, never ORM models, never Pydantic schemas.
- Use tuples rather than lists for collections; frozen means frozen.
- One `Protocol` with the query method, taking value-object ids and returning
  the top-level DTO or `None`:

  ```python
  class BookDetailsQueryProtocol(Protocol):
      async def get_book_details(
          self, book_id: BookId, user_id: UserId
      ) -> BookDetailsView | None: ...
  ```

One port may carry more than one method. Where several endpoints render the same
response schema — the jobs module serves both "this batch" and "the book's
active batch" as a `JobBatchResponse` — give them one DTO and one
`JobBatchQueryProtocol` with a method each, instead of two ports duplicating the
shape.

Sharing one DTO across two endpoints can mean one method fills a field the other
computes. `HighlightLabelQueryProtocol.list_global` hands back
`label_source="global"` and `highlight_count=0` because the router did, while
`list_for_book` resolves both for real. Preserve the constant and say why in the
DTO's docstring; do not start computing it because the field is now in reach.

A paginated view needs both the page and the unpaginated total, which is two
values, not one DTO. Wrap them: `BookListPageView` holds
`books: tuple[BookWithCountsView, ...]` plus `total: int`, and the router reads
`page.books` / `page.total`. Returning a bare tuple from the port would put the
view's shape back in the caller, which is the thing the port exists to stop.

Derive the DTO fields from what the response schema actually needs — read the
router's schema-building function first and work backwards. Do not mirror the
tables.

`datetime` gotcha: if a DTO field is itself named `datetime` (the API has one),
import the type as `from datetime import datetime as dt`, or pyright will
resolve the annotation to the field.

### 2. Write the adapter

In `src/infrastructure/<module>/queries/<view_name>_query.py`. A handful of
targeted selects is fine and preferable to reusing an aggregate finder.

- Take `db: AsyncSession` in the constructor, exactly like a repository.
- Select only the columns you need where the shape is flat; select the ORM
  entity where you need a lot of it.
- `joinedload` for to-many relations you fold into one DTO, and remember
  `.unique()` on the result.
- **Do not build a statement at module scope.** `select(...)` is immutable, so a
  shared base statement looks like the obvious way to let two methods share a
  column list — but `.options(noload(X.rel))` resolves the relationship
  eagerly, and adapters are imported from `containers/shared.py` early enough
  that this configures the ORM mappers before every model is registered. The
  whole suite then dies at collection with `InvalidRequestError: ... failed to
  locate a name`. Build the statement in a small function instead
  (`_book_rows()` in `book_list_query.py`) and call it per query.
- Selecting the ORM entity drags in its `lazy="selectin"` relationships, one
  extra round trip per result set, for data the view never renders. `Book` has
  `tag_groups` configured that way, so both list queries and the book-details
  query pass `noload(BookORM.tag_groups)`. Selecting a column list avoids this
  by construction; selecting the entity means you have to remember.
- Reproduce every filter the old path applied: soft deletion
  (`deleted_at IS NULL`), user ownership, and any "in active use" style
  predicate. Ownership is the easiest to drop by accident — check both the
  parent row's `user_id` and the child rows'.
- Check *where* each filter applied. A path that resolved ids in Python may
  have filtered the resolved entities without filtering the ids they came from,
  and the response then carries both shapes. The note views do exactly this:
  `highlight_ids` is the note's raw link set while `highlights` holds only the
  live, owned rows, so a link to a soft-deleted highlight keeps its id and
  renders as nothing. That is API behaviour, not a bug to tidy up — give the
  DTO both fields and say so in its docstring, rather than filtering once and
  deriving the other.
- Copy an existing finder's `ORDER BY` verbatim rather than tidying it. A bare
  `.order_by(Chapter.chapter_number)` sorts nulls first on SQLite and last on
  PostgreSQL; "fixing" that with `nulls_last()` changes the response on one
  dialect and the OpenAPI check will not notice.
- Return `None` when the root row is absent; let the read use case turn that
  into the domain's NotFound error. When the root row is also the ownership
  check, `None` is what separates "no such book" (404) from "a book with
  nothing in it" (an empty list) — the two are otherwise indistinguishable
  once the aggregate load is gone.
- A view whose data does not all live in Postgres may take the other store's
  collaborator too. `ReadingSessionQuery` is constructed with the file
  repository and the text extractor because a session's `content` is read back
  out of the book's EPUB: that is a fetch, not a decision, and the alternative
  was putting the sessions' xpoints into a DTO that never renders them. Fetch
  the shared blob once per call, not once per row, and let a failed read
  degrade the field rather than the response.

A field the response schema declares but the old router never passed is not an
invitation to start filling it *in the port*. The book-flashcards list used to
serialise `note_id` as `null` because the router omitted it, even though the
schema had the field; the port preserved that, and a follow-up commit added the
field to the DTO and filled it. The highlight search carried the same omission
and was repaired the same way, one commit later. Keep the two apart: the
OpenAPI document is byte-identical either way, so the verification step cannot
tell a faithful port from a behaviour change, and a reviewer reading one commit
should not have to guess which they are looking at.

### 3. Add the read use case

In the same `queries/` package. It wraps the port, and any command the page
triggers:

```python
class GetBookDetailsUseCase:
    def __init__(
        self,
        mark_book_viewed_use_case: MarkBookViewedUseCase,
        book_details_query: BookDetailsQueryProtocol,
    ) -> None: ...
```

If the old read hid a write (marking something viewed, touching a timestamp),
extract that into its own command use case under `commands/` — one operation
per file — and call it from the read use case *before* querying.

### 4. Wire the DI container

- The adapter is infrastructure, so it is provided from `SharedContainer`
  alongside the repositories, with `db=db`.
- The module container declares `providers.Dependency()` for the adapter and a
  `providers.Factory` for the read use case.
- `RootContainer` passes `shared.<name>_query` into the module container.
- Delete dependencies that the removed use case was the only consumer of —
  `rg` for each provider name before removing it.

### 5. Rewire the router

The router injects the **read use case**, never the port, via the existing
`inject_use_case(container.<module>.<name>)` pattern. Map the view DTO to the
response schema in the router; the schema must not change.

Keep the endpoint docstring byte-for-byte identical — FastAPI publishes it as
the operation `description`, so editing it changes the OpenAPI document.

### 6. Delete the old path

Remove the old use case and its DTOs, then `rg` for every name you deleted.
Only remove repository methods or services if they are *fully* dead — verify
with `rg` first. In this spike `highlight_repository.search` stayed (highlight
search still uses it) while the `highlight_grouping_service` provider went.

### 7. Extend the contract if needed

The `queries-are-dead-ends` contract uses wildcards
(`src.application.*.commands` → `src.application.*.queries`), which
import-linter ≥ 2.11 supports, so **a new module's queries package is covered
automatically**. If the project ever pins an older import-linter, the wildcards
must be expanded into an explicit list of packages, and that list must then be
extended for every module that grows a `queries` package.

## The two rules

### Rule 1 — queries never decide (review-enforced)

Adapters select, join, filter, order, group. They do not encode business rules.
There is no static check for this; it is caught in review.

✗ Violation — the label-precedence rule re-implemented in SQL:

```python
label = case(
    (book_style.c.label.isnot(None), book_style.c.label),
    else_=global_style.c.label,
)
```

✓ Correct — reuse the service that owns the rule:

```python
labels = await self.label_resolution_service.resolve_for_book(user_id, book_id)
...
text=resolved.label if resolved else None
```

✗ Violation — a threshold or category baked into a `WHERE`:

```python
.where(ReadingSessionORM.duration_seconds > 300)  # "a real session"
```

✓ Correct — fetch, then ask the domain service what counts.

✗ Violation — a named set of statuses restated as literals in SQL:

```python
.where(JobBatchModel.status.in_(["pending", "running"]))  # "still active"
```

✓ Correct — the set is a domain fact, so the adapter imports it:

```python
from src.domain.jobs.entities.job_batch import ACTIVE_JOB_BATCH_STATUSES
...
.where(JobBatchModel.status.in_(sorted(s.value for s in ACTIVE_JOB_BATCH_STATUSES)))
```

The rule is not "no status filters in SQL"; it is that the adapter must not be
where the set is *defined*. If the read you are porting keeps such a set as a
private constant in the application layer, move it to the domain next to the
enum as part of the port.

Filtering on `deleted_at IS NULL` or `user_id = :me` is **not** a decision:
soft-deleted and other people's rows are not data at all from the caller's
point of view.

### Rule 2 — read DTOs are dead ends (machine-enforced)

A view DTO may reach a router and a response schema. It may never reach a
command.

✗ Violation:

```python
# src/application/library/commands/book_management/update_book_use_case.py
from src.application.library.queries.book_details import BookDetailsView
```

`uv run lint-imports` fails this. If you find yourself wanting it, the command
needs an aggregate loaded from a repository, not a rendering of one.

## Verification checklist

Run all of these from `backend/`:

```bash
uv run pytest                                  # full suite, unchanged tests must pass
uv run pyright                                 # 0 errors — whole project, tests included (what CI runs)
uv run ruff check src tests
uv run ruff format --check src tests
uv run lint-imports                            # all contracts KEPT
```

Then prove the API did not move. Dump the schema on your branch and on a clean
`main`, and compare:

```bash
cd backend && TESTING=1 ADMIN_PASSWORD=x \
  SECRET_KEY=test-secret-key-at-least-32-bytes-long \
  REFRESH_TOKEN_SECRET_KEY=test-refresh-token-secret-key-at-least-32-bytes-long \
  uv run python -c "import json; from src.main import app; print(json.dumps(app.openapi(), sort_keys=True, indent=2))" \
  > /tmp/openapi-branch.json
# repeat on a checkout of main, then:
cmp /tmp/openapi-main.json /tmp/openapi-branch.json
```

It must be byte-identical unless the ticket explicitly changes the API.

Finally, confirm the dead-end rule by inspection as well as by contract:

```bash
rg -n "application\.[a-z_]+\.queries" backend/src/domain \
  backend/src/application/*/commands
```

should print nothing.

## Tests

Test the adapter directly, against the SQLite session from `tests/conftest.py`,
under `tests/unit/infrastructure/<module>/queries/`. Build it with the same
collaborators the container gives it. Cover, at minimum:

- rows with no children still appear (chapters without highlights),
- soft-deleted rows are excluded,
- rows belonging to another user are invisible, both for the root entity and
  for its children,
- any filtering the DTO promises (book-level vs highlight-level flashcards),
- any edge case in the old code you had to preserve.

Endpoint tests stay as they are — they are the regression net proving the port
did not change behaviour.
