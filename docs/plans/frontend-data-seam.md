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
`cancelQueries` — spread across 16 files, with no shared vocabulary:

1. **"A note changed" is written three times.** `NoteEditorForm.tsx`, `NoteViewModal.tsx`
   and `hooks/useNoteLinks.ts` each independently invalidate
   `getGetNotesForBook…QueryKey(bookId)` *and* `getGetNote…QueryKey(noteId)`. Nothing
   enforces the pair. A fourth note mutation that invalidates only the first ships a
   stale list, and there is no test to catch it.
2. **Cache keys travel as props.** `additionalInvalidateKeys` originates in
   `NoteFlashcardSection.tsx` and is threaded through `FlashcardSection` →
   `FlashcardListCard` → `useFlashcardMutations`. A leaf presentational component holds a
   React Query key because no other channel exists.
3. **`getGetBookDetails…QueryKey` appears in four files**, one of which edits that cache
   entry by hand through an untyped cast (`old as { tags: TagInBook[] }`).

That is the whole case. It is a correctness risk with a small, cheap fix.

## Design

One module, `src/data/cache.ts`, exposing invalidation as **entity events** rather than
query keys:

```ts
const cache = useCacheEvents();

cache.noteChanged(bookId, noteId);            // notes-for-book + note detail
cache.tagsChanged(bookId);                    // book details + book tags
cache.flashcardsChanged(bookId, { noteId });  // book details + the owning entity
cache.prereadingChanged(bookId, chapterId);
cache.bookChanged(bookId);
```

It owns the nine query-key getters the app currently reaches for directly, and absorbs
`useBookMutationHelpers` (whose `invalidateBookDetails` / `invalidateBookAndTags` are the
same idea, applied to two cases out of ten). `mutationErrorHandler` moves across with it.

`flashcardsChanged` is what retires `additionalInvalidateKeys`: the caller names the
entity that owns the flashcard, and the prop disappears from four modules.

**Not in scope:** wrapping the 48 generated hooks. Components keep importing them
directly. This module is about *invalidation*, not about hiding the client.

### Lint rule

One rule, narrow enough to be true:

```js
// error outside src/data/cache.ts
'no-restricted-syntax': [
  'error',
  { selector: "CallExpression[callee.property.name=/^(invalidateQueries|setQueryData|refetchQueries)$/]",
    message: 'Express the change as an event in @/data/cache.ts instead.' },
]
```

That enforces the invariant that matters. The originally-planned ban on importing
`@/api/generated` is dropped — it only made sense when every hook was wrapped.

## Sequence

Small enough for two PRs.

**1 — `cache.ts` + notes.** Write the module, reimplement `useBookMutationHelpers` on top
of it, and convert the three note mutation sites. This is the step that proves the design:
if `noteChanged` can't express all three, the shape is wrong.

**2 — everything else.** The remaining 13 files, plus deleting `additionalInvalidateKeys`
from `NoteFlashcardSection` → `FlashcardSection` → `FlashcardListCard` →
`useFlashcardMutations`. Turn the lint rule on.

Two exceptions get an explicit decision rather than a mechanical move:

- **`useTagMutations`'s optimistic update** does `cancelQueries` + `setQueryData` +
  rollback on the book-details entry. That is optimistic-update machinery, not
  invalidation, and it should stay where it is. `cache.ts` covers its `onSuccess`
  invalidation only.
- **`BatchPrereadingToolbar`** reads `query.state.data?.status` inside a `refetchInterval`
  predicate. Polling is not invalidation; leave it alone.

## Verification

`npx tsc --noEmit` and `npm run lint` per PR, plus a manual smoke of the touched tab.

There is no frontend test infrastructure, so the review property is: **for each converted
mutation, the set of query keys invalidated is unchanged, key for key.** That is readable
in the diff as long as mechanical conversion and behaviour changes stay in separate
commits. Where an event deliberately invalidates *more* than the site it replaces —
likely for the two incomplete note sites — say so in the commit message.

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
