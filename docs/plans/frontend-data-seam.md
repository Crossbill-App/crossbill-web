# Frontend cache-invalidation seam

Give cache invalidation one home, so that "a note changed" is expressed once instead of
three times and no component has to hold a React Query key.

**This plan was originally much larger** — one hand-written module per domain noun,
wrapping every generated hook, with components banned from importing `@/api/generated`.
Measuring the justifications killed most of them. What survived is roughly 80 lines. The
[reasoning is below](#why-this-is-small), kept so the larger version is not proposed again
from the same premises.

## The problem, measured

26 cache operations — `invalidateQueries`, `setQueryData`, `refetchQueries`,
`cancelQueries` — spread across 16 files, with no shared vocabulary.

**A hand-written query key has already drifted, and it is a live bug.**
`BookEditModal.tsx` refetches the books list after deleting a book:

```ts
await queryClient.refetchQueries({ queryKey: ['/api/v1/books'], exact: true });
```

`getGetBooksQueryKey()` returns `` [`/api/v1/books/`] `` — with a trailing slash — and
`LandingPage` calls `useGetBooks({ search, offset, limit })`, so the real key is
`` [`/api/v1/books/`, { search, offset, limit }] ``. The literal matches neither: wrong
path, and `exact: true` against a two-element key. Combined with the 5-minute `staleTime`
in `lib/queryClient.ts`, **a deleted book keeps appearing in the list for up to five
minutes.** This is precisely the failure the seam prevents: a key written by hand, never
checked against the generated one, silently matching nothing.

The rest:

1. **"A note changed" is written twice**, in `NoteEditorForm.tsx` and
   `hooks/useNoteLinks.ts`, each invalidating `getGetNotesForBookQueryKey(bookId)` *and*
   `getGetNoteQueryKey(noteId)` with nothing enforcing the pair. (`NoteViewModal.tsx`
   invalidates only the list — correctly, since it deletes the note and refetching a
   removed note's detail would 404. It is a different event, not a third copy.)
2. **Cache keys travel as props.** `additionalInvalidateKeys` originates in
   `NoteFlashcardSection.tsx` and is threaded through `FlashcardSection` →
   `FlashcardListCard` → `useFlashcardMutations`. A leaf presentational component holds a
   React Query key because no other channel exists.
3. **`getGetBookDetailsQueryKey` appears in four files**, one of which edits that cache
   entry by hand through an untyped cast (`old as { tags: TagInBook[] }`).

## Design

One module, `src/lib/cacheEvents.ts`, next to the `queryClient` it acts on. It exposes
invalidation as **entity events** rather than query keys.

The vocabulary is read off the existing call sites, not invented — every event below
exists because some mutation already performs exactly that set of invalidations:

| Event | Invalidates | Replaces |
| --- | --- | --- |
| `bookChanged(bookId)` | book details | `invalidateBookDetails` (8 callers) |
| `tagsChanged(bookId)` | book details, book tags | `invalidateBookAndTags` |
| `noteChanged(bookId, noteId)` | notes-for-book, note detail | `NoteEditorForm`, `useNoteLinks` |
| `noteDeleted(bookId)` | notes-for-book | `NoteViewModal` |
| `booksListChanged()` | books list, recently-viewed | `BookEditModal` (**the bug**), `BookPage` |
| `prereadingChanged(bookId)` | book prereading | `ChapterReviewSection`, `ChapterToolbar` |
| `prereadingBatchChanged(bookId)` | book prereading, active batch | `BatchPrereadingToolbar` (on finish) |
| `prereadingBatchStarted(bookId)` | active batch | `BatchPrereadingToolbar` (on enqueue) |
| `highlightLabelsChanged(bookId)` | book highlight labels | `LabelEditorPopover` |
| `flashcardsChanged(bookId, owner)` | book details, owner's detail | `useFlashcardMutations`, `FlashcardListCard` |

`owner` is `{ noteId } | { highlightId } | { chapterId } | undefined`. That parameter is
what retires `additionalInvalidateKeys`: the caller names the entity that owns the
flashcard instead of passing a query key, and the prop disappears from four modules.

The module absorbs `useBookMutationHelpers` — its `invalidateBookDetails` /
`invalidateBookAndTags` are two of the ten events above — and `mutationErrorHandler` moves
across with it.

**Not in scope:** wrapping the 48 generated hooks. Components keep importing them
directly. This module is about *invalidation*, not about hiding the client.

### What deliberately stays put

Four things use the query cache for something that is not invalidation. Moving them behind
an event vocabulary would misrepresent what they do:

- **`useTagMutations`** — `cancelQueries` + `setQueryData` + rollback on book details.
  Optimistic update machinery. Only its `onSuccess` invalidation becomes `tagsChanged`.
- **`useNoteModals`** — `setQueryData(noteKey, note)` seeds the detail cache from a list
  item so the modal opens without a fetch. Cache seeding, not invalidation.
- **`ReflectionPage`, `ChapterReviewSection`** — `setQueryData` write-through with the
  server's response after a save.
- **`BatchPrereadingToolbar`** — `refetchInterval` predicate reading
  `query.state.data?.status`. Polling.

The lint rule below therefore covers `invalidateQueries` and `refetchQueries` only.
Banning `setQueryData` would flag all four of these, and they have nowhere better to live.

### Lint rule

```js
// error everywhere except src/lib/cacheEvents.ts
'no-restricted-syntax': [
  'error',
  { selector: "CallExpression[callee.property.name=/^(invalidateQueries|refetchQueries)$/]",
    message: 'Express the change as an event in @/lib/cacheEvents.ts instead.' },
]
```

This is what stops the `BookEditModal` failure recurring: with no way to call
`invalidateQueries` outside one file, there is nowhere left to hand-write a key.

The originally-planned ban on importing `@/api/generated` is dropped — it only made sense
when every hook was wrapped.

## Sequence

Three commits, one PR.

**1 — Fix the books-list bug on its own.** Replace the hand-written literal in
`BookEditModal` with `getGetBooksQueryKey()` and `getGetRecentlyViewedBooksQueryKey()`,
switching `refetchQueries({ exact: true })` to `invalidateQueries`. Prefix matching then
covers the paginated key, and marking the list stale is enough — `LandingPage` refetches on
mount, so the `await` before `navigate` is no longer load-bearing. Separate commit because
it is the one behaviour change in this work, and it should be reviewable and revertable
without the refactor around it.

**2 — `cacheEvents.ts` + notes.** Write the module, reimplement `useBookMutationHelpers` on
top of it, convert the three note sites. This step proves the design: if `noteChanged` and
`noteDeleted` cannot express all three without an escape hatch, the vocabulary is wrong and
better to find out at three sites than at sixteen.

**3 — The remaining 13 files, then turn the lint rule on.** Includes deleting
`additionalInvalidateKeys` from `NoteFlashcardSection` → `FlashcardSection` →
`FlashcardListCard` → `useFlashcardMutations`.

## Verification

`npx tsc --noEmit` and `npm run lint` throughout.

There is no frontend test infrastructure, so the review property is: **for commits 2 and 3,
the set of query keys invalidated per mutation is unchanged, key for key.** That is
readable in the diff as long as commit 1 carries the only behaviour change. If any event
turns out to invalidate more than the site it replaces, say so in the commit message rather
than letting it pass as mechanical.

Two things worth checking by hand, since nothing else will:

- **Delete a book** and confirm it leaves the list immediately — the bug fix in commit 1,
  which is invisible to `tsc`.
- **Generate prereading for a book** and watch the batch toolbar, since it is the only
  place where polling and invalidation interact.

## Why this is small

Three of the four original justifications did not survive contact with evidence.

**"Regeneration churns 41 files" — false.** Checked against 12 months of history: 19
regenerations removed hook names. The largest, `2c374432 "Reorganize API routes"`, renamed
**40 hooks and touched 7 non-generated files** (~54 lines). `e3c31743` renamed 27 → 6
files; `e97a6f47` renamed 25 → 1 file. This branch's own regeneration — two module
regroupings plus two renames, about as disruptive as it gets — touched 8 files and 9
import lines. There are 48 distinct hooks across ~60 call sites, so most are used exactly
once and renames do not fan out. The 41-file figure was inferred from the import count and
never observed. A seam would not reduce this to zero either; it would relocate the same
edits into `src/data/`.

**"77 files import the generated client" — misleading.** 36 of them import only DTO types
from `@/api/generated/model`, which carry no cache or client coupling.

**"A fake adapter makes tests possible" — out of scope.** There is no frontend test
infrastructure, and adding it is separate work. This is the one justification that could
bring the larger seam back: wrapping hooks starts paying when something needs to swap the
adapter.

**Long hook names have a cheaper fix.** `useUpdateTagApiV1BooksBookIdTagTagIdPost` is long
because FastAPI derives operationIds from handler name + path + method and the backend
sets no `generate_unique_id_function`. Five backend lines address that directly. Note it
is the one change that *does* touch all 41 runtime importers, since every hook is renamed
at once — but mechanically, in a single sweep.

**What the larger version would have cost:** 48 wrapper hooks and 9 key wrappers across 14
modules, 500–800 lines of hand-written indirection maintained permanently, with no tests to
catch a wrapper that silently drops an option — against ~25 lines of duplicated
invalidation and one badly-threaded prop.

## Revisit if

- Frontend tests arrive and something needs to substitute the API layer.
- A domain noun accumulates enough real client-side logic to justify its own module on its
  own merits, rather than for symmetry.

Neither is true today.

## Related backend work, already done on this branch

Three routing changes that came out of scoping this, none of which the frontend seam
depends on:

- `create_flashcard_for_highlight` moved to a `tags=["flashcards"]` router; it was the
  only flashcard endpoint tagged `highlights`.
- Eight tag operations split out of `reading/routers/highlights.py` into
  `reading/routers/tags.py` with `tags=["tags"]`. A router split, not a domain move — an
  OpenAPI tag is a client-grouping hint, so it does not prejudge where `Tag` belongs.
- The tag group routes moved from `/highlights/tag_group` to `/tag-groups`.

### Still open: where `Tag` belongs

Recorded because it was gathered while scoping, not because anything here resolves it:

- `Tag` carries `user_id` **and** `book_id`; its docstring still says "for categorizing
  highlights within a book", which notes have outgrown.
- `TagGroup` carries `book_id` but **no `user_id`** — the user-scoping rule genuinely
  breaks between the two aggregates in one repository.
- `tag_repository.py` imports `src.infrastructure.notes.orm.associations.note_tags`:
  Reading infrastructure reaching into Notes.
- `TagRepositoryProtocol` has 19 dependents: 12 under `application/reading`, 6 under
  `application/notes`, 1 under `application/library`.

Both `Tag` and `TagGroup` are scoped to a Book and have no lifetime independent of one,
which argues against a standalone bounded context and for treating Tag as owned by
whichever module owns Book, with Reading and Notes as consumers.

### Also outstanding

`add_tag_to_highlight` and `remove_tag_from_highlight` in `tags.py` share ~40 duplicated
lines building the same `Highlight` schema. `reading/schema_mappers.py` is the natural home
for a `map_highlight_to_schema`.
