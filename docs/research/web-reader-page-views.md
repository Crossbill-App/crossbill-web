# What the Web Reader can report for each Page View

Research for #1018, part of the map #1010 (recording the pages actually seen in
a Reading Session). It answers what the Web Reader can capture for a Page View —
where the page starts, as an xpoint, and how long it stayed on screen. It does not
pick a design; that is the grilling ticket #1020.

Researched 2026-11-27.

## Sources

- **Readium TS toolkit, at the versions the frontend pins**: `@readium/navigator`
  2.14.0 and `@readium/shared` 2.8.0 (`frontend/package.json:31-32`). The navigator
  bundles `@readium/navigator-html-injectables` 2.9.2, which holds the in-frame
  column snapper. The installed sources (`node_modules/@readium/*/src`, hoisted to
  the repo root) match upstream: the git blob hashes of `EpubNavigator.ts` and
  `ColumnSnapper.ts` equal those at the `navigator/2.14.0` and
  `navigator-html-injectables/2.9.2` tags of
  [readium/ts-toolkit](https://github.com/readium/ts-toolkit). The links below
  point at those tags.
- **This repo**: `frontend/src/components/reader/`, the web reader's backend
  module, and ADR-0004 (`docs/adr/0004-web-reader-anchors.md`).
- **Web platform**: MDN on the Page Visibility API, `visibilitychange`,
  `Document.hasFocus()` and the Idle Detection API; the WHATWG HTML "has focus
  steps"; MDN browser-compat-data for `IdleDetector`.
- **KOReader** `plugins/statistics.koplugin/main.lua` at `v2026.07.1`, the stable
  release, because it already measures time per page.

Short names used below: **EN** is
[`navigator/src/epub/EpubNavigator.ts`](https://github.com/readium/ts-toolkit/blob/navigator/2.14.0/navigator/src/epub/EpubNavigator.ts)
and **CS** is
[`navigator-html-injectables/src/modules/snapper/ColumnSnapper.ts`](https://github.com/readium/ts-toolkit/blob/navigator-html-injectables/2.9.2/navigator-html-injectables/src/modules/snapper/ColumnSnapper.ts).

Everything about Readium's event order comes from reading the source. None of it
was checked in a running browser. The places where the order is subtle are marked
*(from source)*, and a spike should confirm them.

---

## 1. What `positionChanged` passes, and whether it gives a page start

### The Locator on a page turn (reflowable EPUB)

1. `goForward` / `goBackward` send `go_next` / `go_prev` to the frame
   (EN:1207-1227, EN:1185-1205).
2. The column snapper scrolls by exactly one frame width, snapped to a page
   boundary, and calls `reportProgress()` (CS:622-658). A swipe ends in
   `snapCurrentOffset` → `reportProgress()` (CS:246, CS:255).
3. `reportProgress` sends `progress` with `{ start, end, fragmentId,
   visibleFragmentIds }` (CS:134-150), where
   - `start = scrollLeft / (scrollWidth − innerWidth)`
   - `end = (scrollLeft + innerWidth) / scrollWidth`
4. The navigator's `progress` case (EN:636-641) calls `syncLocation` (EN:1164-1183).
   It takes the **last entry of the position list** in this resource whose
   `progression ≤ start` (`findNearestPositions`, EN:1121-1143), and fires
   `positionChanged` with `thatEntry.copyWithLocations({ progression: start })`
   (EN:1169-1176).

So a page-turn Locator holds:

| Field | Value | Precision |
| --- | --- | --- |
| `href` | the resource | exact |
| `locations.progression` | `start` above: the page's left edge as a fraction of the resource's *scrollable width* | to the page, but see the bias below |
| `locations.position` | copied from the position-list entry before the page | coarse: one per 1024 bytes of XHTML (`backend/src/application/web_reader/queries/publication_positions.py:47`) |
| `locations.totalProgression` | copied from that same entry, **not recomputed** for the page | coarse |
| `locations.fragments` | from the position entry (normally empty) | — |
| `cssSelector`, `domRange`, `partialCfi` (`otherLocations`) | absent | — |
| `text` | absent | — |

The `LocatorLocations` fields are defined in
[`shared/src/publication/Locator.ts:12-43`](https://github.com/readium/ts-toolkit/blob/shared/2.8.0/shared/src/publication/Locator.ts#L12-L43).
The position list itself is the server's, loaded by `positionsFromManifest`
([`Publication.ts:123-135`](https://github.com/readium/ts-toolkit/blob/shared/2.8.0/shared/src/publication/Publication.ts#L123-L135)).

ADR-0004's correction in Amendment 3 ("A reading position usually has no quote at
all") says the same: a page turn arrives as an `href`, a `position`, a
`progression` and no text.

The page's **end** is available, but only through `viewportChanged`: `syncLocation`
writes `progressions: {start, end}` and `positions: [first, last]` into the reflow
viewport (`updateViewport`, EN:1145-1162) just before firing `positionChanged`.
Crossbill drops it: `viewportChanged: () => {}` (`ReadiumReader.ts:447`).

### The Locator on a jump

`go(locator)` (EN:1460-1484) first resets `currentLocation` to the **first
position of the target resource** (EN:1471) and runs `apply()`. Then
`loadLocator` (EN:1370-1424) sends `go_text` (when the target has a quote or a
`cssSelector`), `go_id` (when it has a fragment), or `go_progression`. Each of
those scrolls to the page the target is on, snapped to the page's start, and calls
`reportProgress` (CS:527-588). The Locator that reaches `positionChanged` is
therefore **the same shape as a page turn**: the landed page's start progression,
with the target's own `cssSelector` and text gone. Nothing in it says the move was
a jump rather than a turn.

### Can a page start be mapped to an xpoint?

**Approximately, today.** The current pipeline is: `positionChanged` →
`toLocation` (`frontend/src/components/reader/engine/readium/conversions.ts:66-76`,
which keeps only `position`, `progression`, `totalProgression` and `fragments`) →
`toBrowserLocator` (`frontend/src/components/reader/api/apiLocators.ts`) →
`PUT …/reading-position` → `SaveReadingPositionUseCase._canonical_position`
(`backend/src/application/web_reader/commands/save_reading_position_use_case.py:228-261`).
The anchor service finds no quote and no element, so it falls through to
`AnchorSource.PROGRESSION`
(`backend/src/infrastructure/web_reader/services/xpoint_cfi_position_anchor_service.py:130-146`).
`_text_at_progression` (same file, `:191-202`) takes
`round(progression × len(resource text))` as a **character offset** and quotes the
run there. The use case accepts it at `FUZZY` confidence (`:55-59`).

That page start is off in two ways:

1. **Wrong denominator.** `start` divides by `scrollWidth − innerWidth`, not
   `scrollWidth`. In a resource of *N* screen pages, page *k* (counting from 0)
   reports `k/(N−1)` instead of `k/N`. The error grows towards the end of the
   resource. The last page always reports `1.0`, which `_text_at_progression`
   maps to the resource's **last** text run, not the start of the last page. For
   a 10-page chapter, page 9 says 1.0 where its left edge is at 0.9.
2. **Pixels read as characters.** The fraction is horizontal layout. The backend
   applies it to characters. Images, headings, poems and whitespace make the two
   disagree, by up to a page or more in illustrated chapters.

That is fine for a bookmark, which is all ADR-0004 asked of it ("a reading
position that is off costs a moment finding one's place"). For a Page View it
means a page can be credited to the wrong part of a chapter. Near chapter ends,
where Read Chapter will be decided, it is worst.

**Precise page starts are within reach on the client.** Three ways, from least to
most work:

- **Correct the fraction.** `ReadiumReader` already measures the frame on every
  `positionChanged` (`resourceLayoutIn`,
  `frontend/src/components/reader/engine/readium/chapterProgress.ts:50-63`: `page`
  and `pageCount` from `scrollLeft` / `scrollWidth`). `page / pageCount` is the
  true left-edge fraction. It fixes the denominator bias but not the
  pixels-versus-characters error.
- **Ask Readium for the first visible block.** The injectables answer a
  `first_visible_locator` command (CS:680-684) with
  `findFirstVisibleLocator`
  ([`helpers/dom.ts:95-128`](https://github.com/readium/ts-toolkit/blob/navigator-html-injectables/2.9.2/navigator-html-injectables/src/helpers/dom.ts#L95-L128)):
  a `cssSelector` and the element's `textContent` as `text.highlight`.
  `EpubNavigator` 2.14.0 never sends that command. It only handles the reply
  (EN:519-531), which **overwrites `currentLocation`** — dropping `position` and
  `totalProgression` — and fires `positionChanged` again. Sending it through the
  public `_cframes[0].msg` would therefore cause a second, poorer report. The
  answer is also only paragraph-grained: the first *fully* visible element, or
  the element whose text started on the previous page.
- **Measure the page start in the frame.** The frame windows are already
  reachable (`this.frames`, `ReadiumReader.ts:440`). The first text position at
  the page's top-left can be found with `caretPositionFromPoint` /
  `caretRangeFromPoint`, or by walking text nodes for the first rect inside the
  viewport. From it, build a quote (`text.after`) plus a `cssSelector`, which the
  backend already resolves at `QUOTE` or `ELEMENT` confidence. This is the same
  kind of work `SelectionTracker` does for highlights. ADR-0004 rejected "scraping
  the iframe's DOM on every page turn" for the *reading position*. A Page View
  needs a precision the bookmark never did, so that rejection does not decide this.

## 2. Does `positionChanged` fire once per page shown?

**No: it fires once per settled page plus a number of duplicates and relayout
reports.** Each case:

| Event | Reports | Where |
| --- | --- | --- |
| Page turn inside a resource (key, `next()`/`previous()`, swipe) | one | CS:622-658, CS:246/255 → EN:1164-1183 |
| Turn at the last page of a resource | one report of the **unchanged** page (`go_next` reports even when it did not move), then the new resource arrives (row below) | CS:641-657, EN:1216-1225 |
| Arriving in a new resource (turn or jump) | several *(from source)*: the new frame's `focus` handler reports (FrameManager `showNow` → CS:671-678), `timeline_entries` reports again on the next frame if the resource has ToC fragments (CS:686-690), and `_pong` fires `positionChanged(currentLocation)` with the position-list entry, which is `progression: 0.999999999999` when paging backwards (EN:495-498, EN:1088-1096) | [FrameManager.ts:177-205](https://github.com/readium/ts-toolkit/blob/navigator/2.14.0/navigator/src/epub/frame/FrameManager.ts#L177-L205) |
| Jump into another resource | as above, and *(from source)* the frame can report the resource's start before `loadLocator` scrolls to the target, then the target page | EN:1471-1478 |
| Window or container resize | at least one, often several: the frame's `resize` listener (CS:520-521), the body `ResizeObserver` (CS:461-467) and the `documentElement` style `MutationObserver` (CS:469-497) each call `onWidthChange` → `snapCurrentOffset` → `reportProgress`; the navigator's own `ResizeObserver` (EN:242) may also commit new column CSS, which trips the mutation observer | CS:327-336 |
| Appearance change (font size, spacing, columns) | the same relayout path, through the style mutation | EN:356-375, CS:469-497 |
| Opening the book | reports during `load()` / `resizeHandler()` and from the first `_pong` | EN:322-332; Crossbill treats these as arrival, not moves (`useEbookReader.ts:161-168`, ADR-0004 Amendment 4) |

Hidden, preloaded frames do not report: `onWidthChange` checks `comms.ready`
(CS:329-335), and the navigator drops a `progress` from any frame that is not the
current resource (EN:636-639).

**Two-page spread (reflowable).** With `columns: 2`, one iframe lays out two
columns per screen. `go_next` scrolls by the frame's whole `innerWidth`, so one
`positionChanged` per **spread**. Its progression is the left column's start. The
right column's end is only in `viewportChanged`'s `end`. A Page View in the Web
Reader is therefore one *screen*, which may be two columns.

**Fixed layout.** `changeResource` fires `positionChanged` once per spread with
the first page's position-list entry (EN:1040-1074). The Locator has no
within-page detail, which a fixed page doesn't need.

**What follows.** A Page View recorder cannot treat each `positionChanged` as a
new page. Duplicates are already filtered by JSON equality in
`useReadingPositionWriter.moved` (`frontend/src/components/reader/position/useReadingPositionWriter.ts:156-158`).
The Page View equivalent would be "a different page start than the one on
screen", using the measured page. A relayout ends the current Page View and starts
a new one at whatever the snapper lands on. `snapCurrentOffset` keeps the scroll
offset, not the text, so after a resize the text on screen is different
(CS:190-258). `ReadiumReader.watchLayout` already notes that the last relayout
can land a tick after the last report (`ReadiumReader.ts:478-495`).

## 3. Measuring how long a page stayed on screen

### What the client sends today

`useReadingPositionWriter` (`frontend/src/components/reader/position/useReadingPositionWriter.ts`):

- **Debounced 5 s** (`WRITE_DEBOUNCE_MS`, `:23`; `moved`, `:149-168`). Each move
  restarts the timer, so turning pages faster than every 5 s sends **nothing**
  until the reader rests. Only the last page reaches the server.
- **Heartbeat every 10 minutes** while visible (`HEARTBEAT_MS`, `:27`), polled
  every 5 minutes (`:107-123`). The heartbeat re-sends the latest observation with
  its **original** `recorded_at`.
- **Flush when hidden** (`:127-130`) and a `keepalive` close on unmount
  (`:93-102`, `:134`).
- Only the latest position is held. Earlier pages are not kept.

Server side, each write converts the locator, builds a `PositionIndex` of the
whole EPUB in a thread (`save_reading_position_use_case.py:271-279`, "this runs on
every page turn"), and extends the session. The server's clock is the only clock
a session is measured on (`:163-165`). A new session starts after
`WEB_READING_SESSION_IDLE_SECONDS = 1800` (`backend/src/config.py:172`).

### Server timing successive save-position calls

Not workable without changing the writer. As it stands:

- The 5 s debounce removes exactly the pages a Page View has to tell apart. A
  flicked page never arrives, and the page rested on arrives 5 s late. It is
  timed from that arrival to the next one, which is itself up to 5 s after the
  next turn.
- A page read for 9 minutes with no turn produces no request (the heartbeat is
  10 minutes). The server can see a long gap but not tell reading from absence.
- Removing the debounce means one PUT per turn, each parsing the EPUB and
  building a position index, and arrival time adds network jitter to every
  duration. The departing write is a `keepalive` fetch that may be dropped, which
  would lose the last page's duration.
- In its favour: the server's clock cannot be gamed, which ADR-0004 Amendment 3
  ("Neither clock measures reading") values for *session* length.

### A client-side timer

Workable, and the platform supports it:

- Start the timer on the settled `positionChanged` for a new page start. Stop it
  on the next new page, on hidden or unfocused (section 4), and on close.
  `performance.now()` is monotonic, so it is safe against clock changes.
- A page cannot turn while hidden. The snapper's `go_next` / `go_prev` run inside
  `requestAnimationFrame` (CS:623, CS:642), and MDN says most browsers stop rAF
  callbacks in background tabs. A hidden tab therefore cannot inflate durations
  through page turns. Only a visible page left alone can, which is the idle
  problem in section 4.
- Page Views can be collected in memory and sent in batches, for example
  piggybacked on the existing position write or heartbeat, or flushed on
  `visibilitychange → hidden`, which MDN calls the last reliable event. That
  keeps the server's per-write cost unchanged. The batch can carry each page's
  start locator (or a measured quote) and its duration, and the server converts
  the starts to xpoints in one EPUB parse.
- The trust question changes. Durations would come from the client, so the
  server should bound them: a per-page ceiling, and a total no larger than the
  session's server-measured span.

**Precedent.** KOReader's statistics plugin measures time per page on the device
with exactly these bounds. A page shown for less than `min_sec` (default 5 s) is
not counted. One shown for longer than `max_sec` (default 120 s) is capped at
`max_sec`. Suspend pauses the timer
(`plugins/statistics.koplugin/main.lua:29-30`, `:2560-2617`, `:2694-2703` at
`v2026.07.1`).

## 4. Hidden tab, locked screen, idle reader

### Hidden tab, minimised window, screen off

The Page Visibility API is
[Baseline widely available](https://developer.mozilla.org/en-US/docs/Web/API/Document/visibilitychange_event)
(since April 2021). `document.visibilityState` is `hidden` when "the document's
tab [is] in the background or part of a window that is minimized, or because the
device's screen is off"
([MDN](https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API)).
`visibilitychange` fires on tab switch, navigation, closing the tab or browser,
minimising, and on mobile when switching to another app. MDN calls the transition
to hidden "the last event that's reliably observable by the page". An iframe
shares its parent's visibility, so Readium's frames need no separate handling.

Not settled by the docs:

- **A desktop screen lock** is not named. MDN only says "screen is off". It has
  to be tested per browser and OS.
- **A window covered by another window**: MDN contradicts itself. Its Concepts
  section says "entirely obscured by another window" sends the event, while its
  note says pages become hidden only on tab switch or minimise. Do not rely on it.

### Focus

`document.hasFocus()` on the shell's top-level document follows the HTML
[has focus steps](https://html.spec.whatwg.org/multipage/interaction.html). For
the top-level document they return true exactly when the top-level traversable
"has system focus", **whichever frame inside it holds focus**. It is therefore a
usable "this browser window is the active one" check that is not fooled by focus
moving into a Readium iframe. It catches a visible but unfocused window, for
example a reader looking at another app beside the browser. Whether that should
pause a Page View is a design question, since a reader can read a visible,
unfocused window. Watching `blur` / `focus` on the shell window is riskier.
Browsers commonly fire `blur` on the parent when focus moves into an iframe
(*unverified here*), and every tap on the book does that. Poll `hasFocus()`
instead.

### Idle: visible, focused, nobody there

No portable signal exists.

- The [Idle Detection API](https://developer.mozilla.org/en-US/docs/Web/API/Idle_Detection_API)
  reports `userState` (active/idle) and `screenState` (locked), which is exactly
  this. But it is experimental and Chromium-only: Chrome 94, Edge 114, with no
  Firefox or Safari support (MDN browser-compat-data `api/IdleDetector.json`). It
  also needs a permission prompt after a user gesture, and a secure context.
- Input is not a signal while reading. Nobody touches a page they are reading.
  The page turn *is* the activity.

So idleness has to be bounded, not detected. The realistic tools are a per-page
ceiling on credited time, in the KOReader style, plus pausing on hidden (and
perhaps unfocused). Idle Detection could be an optional extra on Chromium.

### What the frontend already does

- `useReadingPositionWriter`: skips the heartbeat unless
  `document.visibilityState === 'visible'` (`:110`), and flushes the pending write
  on hidden (`:127-130`). It has no focus check, no idle check and no per-page
  timing.
- `useReaderSession` renews the publication cookie on `visibilitychange` and
  window `focus` (`frontend/src/components/reader/opening/useReaderSession.ts:92-109`).
- `AuthContext` refreshes a stale token on `visibilitychange`
  (`frontend/src/context/AuthContext.tsx:168-179`).
- Readium itself tracks visibility only to pause its own message garbage
  collection (`FrameComms.ts:57-93`). It exposes nothing about visibility.

## Most viable approach (input for #1020, not a decision)

The evidence points to **client-side capture**:

- **Page start**: measured in the frame on each settled page change, as a quote
  plus `cssSelector` (or at least `page / pageCount`), not Readium's raw
  `progression`.
- **Duration**: from a `performance.now()` timer that pauses on hidden.
- **Transport**: batched alongside the existing position writes. The backend
  converts the starts to xpoints through the anchor service it already has.

Server timing of position writes cannot see flicking or tell dwelling from
absence, so it does not fit. Readium's `positionChanged` is the right trigger but
needs de-duplication and relayout handling. Idle cannot be detected portably, so
the design will need a per-page time ceiling. KOReader's 5 s / 120 s are the
nearest precedent.

Open for #1020 to decide:

- whether a relayout or a jump starts a new Page View;
- whether an unfocused but visible window pauses the timer;
- the per-page floor and ceiling;
- whether durations from the client are trusted within bounds, or re-checked
  against the session's server-clock span.
