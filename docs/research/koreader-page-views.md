# What KOReader stable exposes for recording Page Views

Research for [#1017](https://github.com/Crossbill-App/crossbill-web/issues/1017),
part of map [#1010](https://github.com/Crossbill-App/crossbill-web/issues/1010).
A Page View is the start xpoint of a page the reader saw, plus how long it was
on screen. This note covers what KOReader gives a plugin for recording one. It
does not pick a design; that is for the grilling ticket.

## Versions checked

| Source | Ref |
| --- | --- |
| KOReader | `v2026.07.1`, the latest release (2026-08-01). The `v2026.07.2` tag has no release object and its tag message says "Identical to 2026.07.1 in order to generate a new nightly artifact"; `compare v2026.07.1...v2026.07.2` is `identical`. |
| koreader-base (`base` submodule at that tag) | `6e4bc81af4e04f78d81677a323a780a71b29702a` |
| crengine (`thirdparty/kpvcrlib/crengine` in base) | `b32a88ffbbf505cf2ea5208c1a49002d70d3609f` |
| Crossbill plugin | local checkout, `_meta.lua` version `0.16.0` |

Unless a line says otherwise, paths are in KOReader at `v2026.07.1`. Short
names used below:

- `rolling` = `frontend/apps/reader/modules/readerrolling.lua`
- `credoc` = `frontend/document/credocument.lua`
- `stats` = `plugins/statistics.koplugin/main.lua`
- `cre.cpp` = koreader-base `cre.cpp`
- `lvdocview.cpp` = crengine `crengine/src/lvdocview.cpp`
- `tracker` = Crossbill `crossbill.koplugin/modules/sessiontracker.lua`

## 1. What `onPageUpdate` passes, and which events fire when

**`PageUpdate` carries one argument: the new page number**, as
`document:getCurrentPage()` returns it. That is the rendered page number in the
current layout, 1-based (`cre.cpp:909-920`). In two-page mode it is the left
page. No xpointer, no old page, and no reason for the change.

`rolling:_gotoPage` (`rolling:1175-1201`) is where nearly every move ends up. It
calls `document:gotoPage` first (`rolling:1194`) and then emits
`PageUpdate(getCurrentPage())` (`rolling:1196`). So inside a `PageUpdate`
handler the document is already on the new page, and `getXPointer()` returns
the new page's start. The screen has not been painted yet; ReaderView only
marks itself dirty (`readerview.lua:1011-1017`).

**In scroll mode no `PageUpdate` fires.** `_gotoPos` emits
`PosUpdate(new_pos, current_page)` instead (`rolling:1159-1164`), and `_gotoPage`
does the same in scroll mode (`rolling:1197-1200`). The statistics plugin
handles this by forwarding `onPosUpdate` to `onPageUpdate` when the page changes
(`stats:2554-2558`). The Crossbill plugin listens only to `onPageUpdate`
(`crossbill.koplugin/main.lua:461-466`), so in scroll mode it does not see any
movement.

What each action emits (page mode):

| Action | Path | Events, in order | Calls `getXPointer()` itself? |
| --- | --- | --- | --- |
| Page turn (tap/swipe/key) | `onGotoViewRel` → `_gotoPage` (`rolling:894-953`) | `PageChangeAnimation`, `PageUpdate(n)`, then `EndOfBook` if it did not move | yes, after `PageUpdate` (`rolling:947`) |
| Go to page / go-to dialog / skim | `GotoPage` → `onGotoPage` (`rolling:756-762`; senders in `readergoto.lua:146-251`) | `PageUpdate(n)` | yes (`rolling:760`) |
| Relative page | `onGotoRelativePage` (`rolling:764-770`) | `PageUpdate(n)` | yes (`rolling:768`) |
| Go to percent | `onGotoPercent` (`rolling:749-754`) | `PageUpdate(n)` | yes (`rolling:752`) |
| TOC entry | `readertoc.lua:985-989` → `GotoXPointer` or `GotoPage` | `PageUpdate(n)` | only on the `GotoPage` branch |
| Internal link, back link | `readerlink.lua:841-898` → `GotoXPointer` / `GotoPage`; `onGoBackLink` → `RestoreBookLocation` → `onGotoXPointer` (`rolling:890-892`) | `PageUpdate(n)` | no on the xpointer path: `onGotoXPointer` sets `self.xpointer = xp`, the link target (`rolling:772-785`) |
| Search result | `readersearch.lua:873-878` calls `ui.rolling:onGotoXPointer` directly | `PageUpdate(n)` | no |
| Next/prev chapter | `rolling:704-743` → `onGotoPage` | `PageUpdate(n)` | yes |
| Footnote shown as popup | no page change | none | — |
| Suspend | `Device:_beforeSuspend` → `UIManager:flushSettings()`, then broadcast `Suspend` (`frontend/device/generic/device.lua:1094-1105`) | `SaveSettings` (via flush), `Suspend` | — |
| Resume | `Device:_afterResume` → broadcast `Resume` (`device.lua:1108-1120`) | `Resume` | — |
| Close | `ReaderUI:onClose` → `saveSettings` (`SaveSettings`), then `CloseDocument`, then the document is closed (`readerui.lua:864-892`) | `SaveSettings`, `CloseDocument` | — |
| Open | `ReaderUI` emits `ReaderReady` (`readerui.lua:517`); `ReaderRolling:onReaderReady` runs `setupXpointer` (`rolling:345-358`, `rolling:205-213`), which jumps to the saved xpointer | `PageUpdate(n)` *during* the `ReaderReady` broadcast, before plugins get `ReaderReady` (plugins register after core modules, `readerui.lua:464-476`) | — |

Two things for telling a jump from a turn:

- **No event says "this was a jump".** Every jump sender calls
  `ui.link:addCurrentLocationToStack()` first (`readertoc.lua:985`,
  `readergoto.lua:153,194,203,212,235,251`, `readersearch.lua:876`,
  `readerlink.lua:848,893-895`), but that only pushes onto
  `ui.link.location_stack` (`readerlink.lua:791-795`) and emits nothing. A
  plugin can tell them apart only by the page delta (a turn moves by
  `getVisiblePageNumberCount()`), or by checking whether
  `#ui.link.location_stack` grew.
- `PageChangeAnimation(forward)` fires before both turns and jumps
  (`rolling:1191-1193`), so it does not help.

`ReadingPaused` / `ReadingResumed` handlers exist only in the statistics plugin
(`stats:2705-2731`). A code search of the repo finds no core sender, so don't
expect them to fire.

## 2. What `getXPointer` costs on a page turn

**I could not measure this on e-ink hardware.** What the source shows:

- **What it does.** `getXPointer` → `text_view->getBookmark()` with
  `precise = true` (`cre.cpp:1019-1026`, default in `lvdocview.h:855`). In page
  mode, `getBookmark` (`lvdocview.cpp:5392-5442`) walks `y` down from the page's
  top pixel. At each step it hit-tests the rendered DOM
  (`createXPointer(lvPoint(0, y), PT_DIR_SCAN_FORWARD_LOGICAL_FIRST)`) and maps
  the result back to a point (`toPoint()`), stopping at the first xpointer that
  lands on the same page. With ordinary text the first step succeeds. When a
  page starts in a tall image or a margin, it can take up to one step per pixel
  of page height. Nothing is re-rendered: `checkPos()` only acts if no position
  is set yet (`lvdocview.cpp:604-627`).
- **KOReader already pays this cost on every turn.** `onGotoViewRel` calls
  `self.ui.document:getXPointer()` right after the turn (`rolling:946-948`), and
  so do `onGotoPage`, `onGotoRelativePage` and `onGotoPercent`. KOReader needs
  it to save `last_xpointer`.
- **A second call on the same page is a cache hit.** `CreDocument` wraps
  `getXPointer` in a per-page "tag" cache (`credoc:1929`). `gotoPage` sets the
  tag to `"page"..n` (`credoc:1881`, the wrapper is at `credoc:1954-1966`), and a
  repeat call returns the stored result from a Lua table (`credoc:1967-1987`). A
  plugin calling `document:getXPointer()` inside `PageUpdate` pays the native
  call. Then `ReaderRolling`'s own call at `rolling:947` is the cache hit. On a
  page turn the total native work stays the same. The cache is on unless the
  user sets `use_cre_call_cache = false` (`credoc:1642`).
- **Where it does cost extra.** On `onGotoXPointer` jumps (links, search, TOC by
  xpointer) and after a re-render, `ReaderRolling` does not call `getXPointer`,
  so a plugin call there is a real native call. These moves are rare compared
  with turns.
- **The 60 s throttle in the plugin** (`tracker:33`, applied at
  `tracker:298-305`) predates any of this reasoning. In page mode it saves at
  most one cached lookup per turn.
- **How to measure on a device.** Set `use_cre_call_cache_log_stats = true` in
  `settings.reader.lua`. On document close, `CreDocument` logs per-function hit
  and miss counts with milliseconds per call (`credoc:1647`, report built in
  `getCallCacheStatistics`, dumped by the `close` wrapper at `credoc:2047-2050`).
  The "By call times (hits | misses)" lines give `getXPointer`'s miss cost on
  the user's hardware.

I found no KOReader issue or PR that reports `getXPointer` timings.

## 3. Turning page numbers into xpoints in bulk (`getPageXPointer`)

**`document:getPageXPointer(page)` exists** (`credoc:888-890` →
`cre.cpp:1028-1039` → `LVDocView::getPageBookmark(page-1, precise=true,
internal)` at `lvdocview.cpp:5477`). It runs the same scan as `getBookmark`,
but on any page from the page table (`m_pages[page_num]`). It does not move the
view, so a loop over many pages does not navigate or repaint. Each call costs
about what a cache-missing `getXPointer` costs. Results go in the global call
cache keyed by arguments (it falls under the `get*` → `cache_global` rule,
`credoc:1936`), and that cache is cleared on any `set*` call or re-render.

KOReader itself calls it one page at a time: bookmarks
(`readerbookmark.lua:388`), go-to (`readergoto.lua:305`), handmade TOC
(`readerhandmade.lua:483,601`), and per chapter in
`ReaderToc:getPagePagemapIndex` (`readertoc.lua:660`). I found no in-tree loop
over a whole book.

**The catch: a page number means something only in the layout it was recorded
in.** `getPageXPointer(n)` answers for the *current* rendering. Converting at
session end is only right if nothing re-rendered in between. A plugin can check
that with `document:getDocumentRenderingHash()` (`credoc:328-333`,
`cre.cpp:841`), the value `ReaderRolling` itself compares to detect a re-render
(`rolling:1032-1035`). Storing the hash next to each recorded page number lets
the plugin convert pages recorded under the current hash and know which ones it
cannot convert.

## 4. Page numbers when font, margins or orientation change

The page count and every page number change. The xpointer stays put:
`ReaderRolling` keeps `self.xpointer` and re-seeks to it.

Font, spacing and margin changes emit `UpdatePos` (`readerfont.lua:191-224`,
`readertypeset.lua:125-171`). Orientation goes through `SetRotationMode` →
`SetDimensions` (`readerview.lua:892-916`) → `ReaderRolling:onSetDimensions` →
`onUpdatePos` (`rolling:1098-1118`). Both land in `ReaderRolling:updatePos`
(`rolling:1028-1067`), which compares the rendering hash. Then one of two paths
runs.

**Full re-render** (partial re-rendering off, or the book can't use it):

1. `_gotoXPointer(self.xpointer)` → `PageUpdate(new page in new numbering)`
   (`rolling:1057`)
2. `DocumentRerendered` (`rolling:1058`); `document:getPageCount()` now gives
   the new total

The order is documented as something statistics relies on (`rolling:1055-1056`,
`stats:196-231`).

**Partial re-render** is on by default (`cre_partial_rerendering`,
`rolling:256-260`). It applies to EPUBs with a cache file and at least two
`DocFragment`s (crengine `lvtinydom.cpp:5303-5323`), which covers most EPUBs:

1. `DocumentPartiallyRerendered(first_partial_rerender)` (`rolling:1632-1649`).
   Page numbers and TOC are invalid from here on, and statistics stops
   counting pages (`stats:233-243`).
2. As fragments re-render on draw, `PageUpdate` fires with page numbers taken
   from a half-rendered document (`rolling:1684-1689`).
3. When the user is idle, the book re-renders fully in a background process.
   KOReader then **reloads the document seamlessly**:
   `ReaderUI:reloadDocument(nil, true)` (`rolling:1867-1868`). That emits
   `PreserveCurrentSession`, then `CloseDocument`, then builds a new
   `ReaderUI`, plugin instances included, and sends `ReaderReady`
   (`readerui.lua:940-960`). `ui.reloading` is true while it reopens
   (`readerui.lua:958`, cleared at `readerui.lua:524`).

For the Crossbill plugin today, this means a font change in an EPUB ends the
session with `"document_close"` and starts a new one on the reload's
`ReaderReady` (`main.lua:453-482`). `PreserveCurrentSession` is the event that
tells a reload apart from a real close.

## 5. Could `page_stat_data` serve as the live source?

**Schema** (`stats:405-419`, `DB_SCHEMA_VERSION = 20221111` at `stats:35`):

```sql
page_stat_data(id_book integer, page integer, start_time integer,
               duration integer, total_pages integer,
               UNIQUE (id_book, page, start_time))
```

`start_time` is `os.time()`, in whole seconds. `total_pages` is the page count
when the row was collected (`stats:932-948`, bind at `stats:945`). A `page_stat` view rescales rows
to the book's current page count by proportion (`stats:435-451`). The book row
is matched by title, authors and partial md5 (`stats:464-484`).

**What it records, and what it leaves out:**

- Page numbers only. No xpointer, no rendering hash.
- A page's duration is the time until the next page change. Durations under
  `min_sec` (default 5 s) are not stored, and durations over `max_sec` (default
  120 s) are cut to `max_sec` (`stats:29-30`, `stats:2605-2620`). Skimmed pages
  disappear, and long dwell times are capped.
- A suspend pause is added to the current page's start time
  (`stats:2694-2731`), so the time asleep is not counted.
- It counts nothing from the first partial re-render until the reload
  (`stats:233-243`). It also stops writing for finished books when "freeze
  finished books" is on (`stats:191-194`, `stats:913`), and when the user turns
  statistics off.

**When it writes** (`insertDB`, `stats:912-997`). Rows are kept in memory in
`self.page_stat` and written to the database:

- every 50 page turns (`MAX_PAGETURNS_BEFORE_FLUSH`, `stats:28`, `stats:2626-2634`)
- on `Suspend` (`stats:2694`)
- on `CloseDocument` (`stats:2672-2675`)
- on `SaveSettings`, which fires on the autosave interval, on suspend and on
  close (`stats:2689-2692`)
- on `DocumentRerendered` when the page count changed (`stats:224-227`)
- when its menus open

**On layout changes.** The pending rows are flushed under the old
`total_pages` before the new count is stored (`stats:196-231`, comment walks
through an example). Rows from before and after a font change therefore stay
internally consistent. There is still no way to map an old row to an xpoint
exactly, only by proportion.

**Can another plugin read it?** Yes, in two ways. Neither is a supported API.

- The file: `DataStorage:getSettingsDir() .. "/statistics.sqlite3"`
  (`stats:27`), opened with `require("lua-ljsqlite3/init")` (`stats:13`). It
  uses WAL where the device allows (`stats:456-460`), and statistics opens and
  closes a connection per write. A read-only reader would rarely collide with
  it. The schema is internal and versioned by `PRAGMA user_version`.
- The live instance: plugins register under their name (`readerui.lua:94-104`,
  `readerui.lua:474`), so `self.ui.statistics` is the running
  `ReaderStatistics`. Its fields `page_stat`, `curr_page`, `data.pages` and
  `id_curr_book` are plain Lua tables and fields. These are internals that can
  change in any release.

Whatever we read from it would still have to be converted from page numbers to
xpoints, with the same layout problem as section 3, and with the 5 s floor and
120 s cap built into the durations.

## What looks most viable (not a decision)

The cheapest route that also gives exact xpoints looks like this:

- Track page changes in the plugin. Handle `onPageUpdate`, and `onPosUpdate`
  for scroll mode.
- On each change, call `document:getXPointer()`. In page mode, on a turn, that
  call costs the same native work KOReader already does: ours misses the cache
  and `ReaderRolling`'s own call becomes the hit. That would make the 60 s
  throttle unnecessary for this purpose.
- Close the previous Page View with the time since its start, minus any
  `Suspend`/`Resume` gap.

A fallback that pays for xpoints only at the end:

- Record page numbers plus `getDocumentRenderingHash()`.
- At session end, convert them with `getPageXPointer(n)` for pages whose hash
  matches the current one.

Its cost is one `getBookmark`-sized call per distinct page at the end. It loses
the pages recorded under an older layout.

The statistics database looks like the weakest source. It has no xpoints, it
cuts durations at both ends, it goes quiet during partial re-renders, and its
schema is private.

Whatever is picked has to deal with partial re-rendering and its seamless
reload, which tear down the plugin instance in the middle of a session.

## Could not establish

- How long `getXPointer` / `getPageXPointer` actually take on the user's e-ink
  device. The call-cache stats setting in section 2 is the way to measure it.
- Whether a Kobo/PocketBook firmware quirk ever skips `Suspend`. The tracker
  comment says `onSuspend` "is not reliable on PocketBook" (`tracker:24-26`); I
  did not verify that against device code.
- The order in which plugins receive events, beyond "core modules first, then
  plugins sorted by path" (`pluginloader.lua:289`). Whether `crossbill.koplugin`
  runs before `statistics.koplugin` depends on where each is installed.

## Sources

- KOReader `v2026.07.1`: <https://github.com/koreader/koreader/tree/v2026.07.1>
  - `frontend/apps/reader/modules/readerrolling.lua`, `readerview.lua`,
    `readerlink.lua`, `readertoc.lua`, `readergoto.lua`, `readersearch.lua`,
    `readerfont.lua`, `readertypeset.lua`, `readerbookmark.lua`,
    `readerhandmade.lua`
  - `frontend/apps/reader/readerui.lua`, `frontend/document/credocument.lua`,
    `frontend/device/generic/device.lua`, `frontend/pluginloader.lua`
  - `plugins/statistics.koplugin/main.lua`
- koreader-base `cre.cpp` at `6e4bc81a`:
  <https://github.com/koreader/koreader-base/blob/6e4bc81af4e04f78d81677a323a780a71b29702a/cre.cpp>
- crengine at `b32a88ff`:
  <https://github.com/koreader/crengine/blob/b32a88ffbbf505cf2ea5208c1a49002d70d3609f/crengine/src/lvdocview.cpp>,
  `crengine/include/lvdocview.h`, `crengine/src/lvtinydom.cpp`
- Crossbill plugin: `crossbill.koplugin/main.lua`,
  `crossbill.koplugin/modules/sessiontracker.lua`
