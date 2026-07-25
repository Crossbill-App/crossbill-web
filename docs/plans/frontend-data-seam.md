# Frontend data-access seam

Migrate direct `@/api/generated` usage behind hand-written modules named after domain
nouns, so that query keys, cache invalidation and payload unwrapping have one home each.

Branch: `frontend-data-seam`.

## Measured starting point

| Fact | Count |
| --- | --- |
| Files importing `@/api/generated` at all | 77 |
| …of which import **only** types from `@/api/generated/model` | 36 |
| Files importing the **runtime** client (hooks, query-key getters) | **41** |
| `invalidateQueries` / `setQueryData` / `refetchQueries` call sites | 16 / 7 / 2, across 16 files |
| Existing insulation | `hooks/useBookMutationHelpers.ts`, 48 lines |

The 41 runtime importers are the migration surface. Type-only importers are out of scope
(see *Decisions*).

## Concrete problems this closes

1. **"A note changed" is written three times.** `NoteEditorForm.tsx`, `NoteViewModal.tsx`
   and `hooks/useNoteLinks.ts` each independently invalidate
   `getGetNotesForBook…QueryKey(bookId)` plus `getGetNote…QueryKey(noteId)`.
2. **Cache keys travel as props.** `additionalInvalidateKeys` originates in
   `NoteFlashcardSection.tsx` and is threaded through `FlashcardSection` →
   `FlashcardListCard` → `useFlashcardMutations`. A leaf presentational component is
   holding a React Query key.
3. **`getGetBookDetails…QueryKey` appears in four files**, with the book-details cache
   entry mutated by hand (`old as { tags: TagInBook[] }`) in `useTagMutations.ts`.
4. **Regeneration blast radius.** `npm run api:generate` currently churns names across 41
   files. After the seam it can only churn `src/api/generated` and `src/data`.

## What the seam does *not* fix

Two things were initially attributed to the missing seam and turn out to have other causes.
Recorded here so they are not re-litigated mid-migration.

**Generated hook names.** `useUpdateTagApiV1BooksBookIdTagTagIdPost` is long because
FastAPI derives `operationId` from function name + path + method. The backend sets no
`operation_id` and no `generate_unique_id_function`. Nothing in this plan shortens those
names; the seam only stops them from reaching the render tree.

*Follow-up worth having, but not now:* adding `generate_unique_id_function` to the app
would yield `useUpdateTag`. Done today it is a mechanical rename across 41 files that
collides with this migration; done after the seam it touches only `src/data/**`. Order
matters — seam first.

**The `createFlashcard` callback injection.** `useFlashcardMutations` takes the create
call as a caller-supplied callback because the four create endpoints take different path
parameters (`bookId` / `noteId` / `highlightId` / `chapterId`). That is API shape, not
module grouping. A `data/flashcards.ts` can still remove the injection by dispatching on
a discriminated source union — but that is a frontend design choice made inside step 3,
not something the seam grants automatically.

## Relationship to the generated module layout

orval runs in `mode: 'tags-split'`, so generated modules follow OpenAPI tags — which come
from `APIRouter(tags=[...])`, not from URL prefixes.

**Flashcards were already grouped correctly.** Six routers across four different prefixes
(`/books`, `/notes`, `/chapters`, `/flashcards`) all carry `tags=["flashcards"]` and land
in one generated module. Exactly one endpoint was misfiled: `create_flashcard_for_highlight`,
defined inside `reading/routers/highlights.py` under `tags=["highlights"]`.

*Fixed.* Moved to `learning/routers/highlight_flashcards.py` (`prefix="/highlights"`,
`tags=["flashcards"]`), mirroring the existing `note_flashcards.py`. The URL and
`operationId` are byte-identical, so the hook keeps its name and only relocates from
`generated/highlights/highlights.ts` to `generated/flashcards/flashcards.ts`. 517 backend
tests pass. On the next `npm run api:generate`, one frontend import line changes.

**Tags are a genuine misgrouping, but the fix is smaller than a bounded-context move.**
Eight tag operations — `get_tags`, `create_tag`, `update_tag`, `delete_tag`, both
tag-group endpoints and both tag↔highlight association endpoints — are defined inside
`reading/routers/highlights.py` under `tags=["highlights"]`, so they generate into
`highlights.ts`.

The key separation: **an OpenAPI tag is not a bounded context.** Splitting those eight
endpoints into a `tags=["tags"]` router — which can stay under `reading/` — yields
`generated/tags/tags.ts` without deciding where Tag belongs in the domain. It is a
router-file change, not a domain move.

That decision is therefore *not a prerequisite for this migration*. `src/data/tags.ts`
exists and behaves identically whether its endpoints come from `highlights.ts` or
`tags.ts`; only its import lines differ. Sequence the backend question independently.

### Evidence for the open backend question

Recorded because it was gathered while scoping this work, not because this plan resolves it:

- `Tag` carries `user_id` **and** `book_id`; its docstring still says "for categorizing
  highlights within a book", which notes have since outgrown.
- `TagGroup` carries `book_id` but **no `user_id`** — the user-scoping rule genuinely
  breaks between the two aggregates in one repository.
- `tag_repository.py` imports `src.infrastructure.notes.orm.associations.note_tags`:
  Reading infrastructure reaching into Notes.
- `TagRepositoryProtocol` has 19 dependents: 12 under `application/reading`, 6 under
  `application/notes`, 1 under `application/library` (`get_book_details_use_case`).

Both Tag and TagGroup are scoped to a Book and have no lifetime independent of one, which
argues against a standalone context and for treating Tag as owned by whichever module owns
Book, with Reading and Notes as consumers.

## Decisions taken

- **One hook per operation**, not a facade per noun. `data/notes.ts` exports
  `useNotesForBook`, `useNote`, `useCreateNote`, `useUpdateNote`, `useDeleteNote`.
  A literal `useNotes(bookId)` facade cannot hold the queries without breaking the Rules
  of Hooks — `notes.list(params)` would be a conditional hook call — and splitting into
  "facade for mutations, hooks for queries" buys grouping at the cost of two idioms.
  One idiom, one signature per hook, tree-shakeable.
- **DTO types stay generated.** `import type { TagInBook } from '@/api/generated/model'`
  remains legal everywhere; those types are the wire contract and carry no cache or
  client coupling. The lint rule bans the runtime modules only. This keeps the migration
  at 41 files instead of 77 and avoids a hand-maintained re-export list.
- **Test infrastructure is out of scope.** The frontend has none today; adding it is a
  separate piece of work and is not an argument used here. The seam is justified by
  invalidation ownership, regeneration blast radius, and keys-as-props on its own.

## Target structure

```
src/api/
  axios-instance.ts, config.ts, token-manager.ts   # unchanged
  generated/                                        # orval output; imported by src/data/** only
src/data/
  keys.ts             # domain-named query keys, wrapping the orval getters
  cache.ts            # useCacheEvents(): semantic invalidation + mutationErrorHandler
  notes.ts  tags.ts  flashcards.ts  books.ts  highlights.ts  highlightLabels.ts
  prereading.ts  jobs.ts  reflections.ts  readingSessions.ts  chapters.ts
  chat.ts  bookmarks.ts  session.ts
```

`keys.ts` exists to break the import cycle: nouns need each other's keys (a tag mutation
invalidates book details), so keys live below every noun module rather than inside one.

### Module conventions

Each `data/*.ts` module, and nothing else:

- imports from `@/api/generated/**`;
- owns the query keys for its noun (via `keys.ts`);
- performs the orval unwrap idiom — the axios mutator already unwraps to the payload, so
  a list hook returns `data?.items ?? []` rather than making every caller repeat it;
- names things in domain terms: `useNotesForBook(bookId, params)`, not
  `useGetNotesForBookApiV1BooksBookIdNotesGet`.

It does **not** add caching policy, retries, or a repository abstraction beyond the above.
The seam is deliberately shallow; the goal is one home per concern, not a new framework.

### Semantic invalidation

`data/cache.ts` replaces key-passing with entity events:

```ts
const cache = useCacheEvents();
cache.noteChanged(bookId, noteId);            // notes-for-book + note detail
cache.tagsChanged(bookId);                    // book details + book tags
cache.flashcardsChanged(bookId, { noteId });  // book details + the owning entity
cache.prereadingChanged(bookId, chapterId);
```

`flashcardsChanged` is what retires `additionalInvalidateKeys`: the caller states which
entity owns the flashcard, not which query key to invalidate.

### Lint enforcement

`no-restricted-imports` in `eslint.config.*`:

```js
patterns: [{
  group: ['@/api/generated/*', '!@/api/generated/model'],
  message: 'Import from @/data/<noun> instead. Only src/data may touch the generated client.',
}]
```

with an override switching it off for `src/data/**`. `npm run lint` runs with
`--max-warnings 0`, so a `warn` phase buys nothing. The rule lands in step 1 as `error`
with an explicit allowlist of the files not yet migrated, and each step shortens that
list. Remaining work stays visible in the config and cannot silently regress.

## Sequence

Each step is a self-contained PR. Steps 2–7 are import rewiring plus key ownership; any
change in observable behaviour must be a separate commit whose subject says so.

**0 — Backend flashcard re-tag.** *Done on this branch.* Regenerate with
`npm run api:generate` before step 3 so `data/flashcards.ts` imports one module.

**1 — Foundation.** Add `keys.ts` and `cache.ts`. Reimplement `useBookMutationHelpers` as
a thin wrapper over `useCacheEvents` so no call site changes yet. Add the lint rule with
the full 41-file allowlist.

**2 — notes** (11 files). Retires the triplicated "note changed". Largest single win.

**3 — flashcards** (6 files). Retires `additionalInvalidateKeys` across four modules, and
decides whether to replace the `createFlashcard` callback with a source union. Depends on
step 2 (`NoteFlashcardSection`).

**4 — tags** (5 files). Move only. All three current strategies are preserved verbatim:
the optimistic `setQueryData` on book details in `useTagMutations`, the local-state sync
in `useImmediateTagMutation`, and the create-only path in `useNoteTagField`. Unifying
them is a behaviour change and belongs in a follow-up — see *Risks*.

**5 — prereading + jobs** (4 files). The polling cluster in `BatchPrereadingToolbar`
(three cache ops, including the only two `refetchQueries` and a `refetchInterval`
predicate reading `query.state.data?.status`).

**6 — books, highlights, highlightLabels** (~11 files, several already touched above).

**7 — reflections, readingSessions, chat, bookmarks, session** (~9 files).

**8 — close the seam.** Empty the lint allowlist, delete `useBookMutationHelpers`, add a
short `src/data/README.md` stating the one rule: components import `@/data`, never
`@/api/generated`.

## Verification

Per PR: `npm run lint`, `npx tsc --noEmit`, and a manual smoke of the touched tab.

Whole-migration success criterion, checkable mechanically: running `npm run api:generate`
produces a diff confined to `src/api/generated/**`.

Because there is no automated coverage, the review discipline carries the weight: for
steps 2–7 the reviewer should confirm that the *set of query keys invalidated per
mutation* is unchanged, key for key. That is a readable property of each diff as long as
mechanical moves and behaviour changes stay in separate commits.

## Risks

- **Tag optimistic update.** `useTagMutations` mutates the book-details cache entry
  through an untyped `old as { tags: TagInBook[] }` cast. Moving it into `data/tags.ts`
  invites typing it against `BookDetails` — resist during step 4, do it after.
- **`useNoteTagField` vs `useImmediateTagMutation` are not accidentally different.** Notes
  defer tag linking to the note's own save; highlights link immediately via dedicated
  endpoints. The seam gives them a shared `useCreateTag` primitive; it does not and should
  not merge them. The existing docstring is correct.
- **`BatchPrereadingToolbar` reads query state** inside a `refetchInterval` predicate.
  Moving that behind `data/jobs.ts` needs the predicate to keep receiving the live query
  object, not a snapshot.
- **Scope creep.** Every step will surface a tempting refactor of the component it touches.
  The rule for this branch: rewire imports, move keys, move invalidation. Nothing else.
