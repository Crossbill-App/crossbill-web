# ADR-0003: One list-length strategy — book content renders whole, library listings paginate

- **Status:** Accepted
- **Date:** 2026-08-30
- **Applies to:** `frontend/`
- **Resolves:** #670 (UI audit finding A7, part of #661)

## Context

Two list-length strategies grew side by side, with no stated rule separating
them.

**Paginated**, offset/limit + a MUI `<Pagination>` + a page number in the URL:

| View | Page size | Where |
| --- | --- | --- |
| Library grid | 32 | `pages/LandingPage/LandingPage.tsx` |
| Reading sessions tab | 30 | `pages/BookPage/ReadingSessions/ReadingSessionsPage.tsx` |

**Rendered whole**, every row at once:

| View | Source |
| --- | --- |
| Highlights tab | `BookDetails.chapters[].highlights[]` |
| Notes tab | `GET /books/{id}/notes` (`CollectionResponse`, no paging) |
| Flashcards tab | derived from `BookDetails.chapters[].highlights[].flashcards` |
| Structure tab | derived from `BookDetails.chapters[]` |

The highlights tab is the longest page in the app and the only long one with
neither paging, virtualisation, nor a result count. That inconsistency read as
an oversight, so the question was whether to paginate the book tabs.

### What the numbers say

Measured against a real library of 32 books and 824 live highlights:

| Metric | Value |
| --- | --- |
| Highlights in the largest book | 170 |
| Highlights in the average book | 32 |
| Highlights, p95 book | ~72 |
| Books over 300 highlights | 0 |

A highlight row costs roughly 15–25 MUI elements and their emotion `sx`
resolution. It renders no markdown, loads no images, and issues no per-row
query — every field comes from the already-fetched book payload. So the
largest page in the app today is around 4,000 elements of pure DOM and style
cost, with no network work behind it.

### What pagination would actually cost

Highlights have **no list endpoint**. They ride inside
`GET /books/{book_id}` → `BookDetails.chapters[].highlights[]`
(`infrastructure/library/queries/book_details_query.py`), and seven consumers
read that array:

- the Highlights, Flashcards, and Structure tabs
- `Notes/NoteViewDialog.tsx`, resolving a note's linked highlights
- the highlight dialog's prev/next (`hooks/useHighlightDialog.ts`)
- the chapter sidebar's per-chapter counts (`useHighlightsPageData`)
- the MCP server's `get_highlights` tool, which falls back to the full book
  payload when given no search text

Paginating the payload breaks all seven **silently** — they under-report
rather than error.

## Decision

**Content bounded by a book renders as one continuous page. Listings
unbounded by the user's collecting paginate.**

| Side | Views | Why |
| --- | --- | --- |
| Renders whole | Highlights, Notes, Flashcards, Structure, Reflection tabs | A book bounds its own highlights. The set has a ceiling the reader already understands: the book. |
| Paginates | Library grid, Reading sessions | A library grows without limit as the user collects, and sessions accumulate for as long as the book is read. |

The rule is about **what bounds the set**, not about how long it happens to be
today.

### Consequence for filtering

Because a book tab holds its whole set in memory, its filters are correct
client-side, and they must stay that way. `HighlightsPage` filters by tag,
label, and date range over the full chapter tree; that is sound precisely
because nothing is missing from it.

**If a book tab is ever paginated, its filtering and sorting must move
server-side in the same change.** Filtering page 1 of 6 in the browser gives
silently wrong results — the user sees "3 matches" when there are 40. This is
the real reason to avoid paginating these tabs, and it is why the decision is
recorded here rather than left to taste.

The one filter this does not cover is the in-book highlight *search*, which is
already server-side and which replaces the active filters rather than
intersecting them. That defect predates this ADR and is tracked as #687.

### Result counts

Every list states how many rows it is showing. The unfiltered totals are
already permanently on screen in `BookTitle/BookStatsStrip.tsx`, which renders
above the tab bar on every tab, so a tab's own header carries **only the count
of rows it is currently rendering** — not a `shown of total` pair, which would
duplicate the strip.

The count lives in `common/PageHeader.tsx`'s control row, beside the sort
toggle, and goes through `utils/counts.ts`'s `countLabel` so plurals stay in
one place.

## Alternatives considered

- **Paginate everything.** Rejected: it requires carving a
  `GET /books/{id}/highlights` list endpoint out of `BookDetailsQuery`,
  splitting the `BookDetails` payload, re-sourcing four tabs plus the dialog's
  prev/next and the sidebar counts, moving tag/label/date filtering
  server-side, regenerating the Orval client, and fixing the MCP server — to
  shorten a 170-row page nobody has complained about.
- **Virtualise the book tabs.** Rejected for now; see the trigger below.
- **Make `BookStatsStrip` filter-aware** so one count serves both. Rejected:
  the strip is book-level and shared across six tabs, so coupling it to the
  highlights tab's filter state would make it wrong on the other five.

## Explicitly NOT adopted

- **Virtualisation** (`react-window`, `@tanstack/react-virtual`). Nothing in
  the app is virtualised today, and the highlights page is a poor first
  candidate — see below.
- **Infinite scroll / cursor pagination.** No `useInfiniteQuery` anywhere, and
  no cursor pagination on the backend; every paginated endpoint is
  offset/limit with a `total`. A second paging idiom would cost more
  consistency than it buys.

## The virtualisation trigger

Virtualisation on the highlights page is not a library install. Rows unmount
when scrolled out of view, and three navigation paths depend on them being in
the DOM — all routed through `components/animations/scrollUtils.ts`'s
`scrollToElementWithHighlight`, which waits 100 ms, calls `getElementById`,
and **does nothing at all if the element is absent**:

| Path | Anchor | Where |
| --- | --- | --- |
| Chapter sidebar click | `#chapter-<id>` | `common/useBookTabFilters.ts` |
| Mobile dialog close, scrolling back | `#highlight-<id>` | `hooks/useHighlightDialog.ts` |
| Bookmark sidebar jump | `#highlight-<id>` | `Highlights/HighlightsPage.tsx` |

Four further obstacles: rows are variable-height (1–40 words of text, a footer
that wraps at `sm`, an unbounded tag-chip list), the page scrolls the window
rather than a container, `FadeInOut`'s `motion.div` wraps the `<Outlet />`,
and `PullToRefresh` applies a `translateY` to an ancestor. Transformed
ancestors are the usual source of windowing measurement bugs.

So the failure mode of premature virtualisation here is *silent broken
navigation*, not a slow page.

**Revisit when either holds:**

1. Any single book passes **500 live highlights** — roughly 3× today's worst
   case, and about where 10,000 DOM elements starts to show:

   ```sql
   select max(c) from (select count(*) c from highlights
                       where deleted_at is null group by book_id) s;
   ```

   As of 2026-08-30 this returns **170**.

2. A user reports the highlights tab feeling slow.

Before reaching for windowing, exhaust the cheap fixes first — memoising
`HighlightCard` and capping `TagChipList` cost nothing and target the same
per-row expense.

## Consequences

**Good**

- One rule, stated, with a reason that survives the next long book.
- No backend work, no new endpoint, no `BookDetails` split, no MCP breakage.
- Client-side filtering on the book tabs stays correct by construction.
- Result counts make list length legible, which was the audit's actual
  complaint.

**Costs**

- The highlights tab's DOM cost grows linearly with the book. Accepted, with
  the trigger above as the release valve.
- The rule has to be *applied*, not inferred: a future list needs someone to
  ask which side of the boundary it falls on.

**Open, tracked elsewhere**

- **#683** — highlights with a null `chapter_id` are dropped from the chapter
  tree and so never render, while `BookDetails.highlight_count` counts them.
  Six such highlights exist across two books, so a tab's rendered count is
  currently below the strip's total on those books. #683 lands first, or the
  new count reads as a bug in itself.
- **#687** — the in-book highlight search replaces the active filters instead
  of intersecting them, and silently caps at 100 matches while reporting that
  cap as `total`. Independent of this ADR, but it is why the count in the
  header reports only rendered rows during a search.
