# ADR-0004: Position anchors for the web reader

- **Status:** Accepted
- **Date:** 2026-09-07
- **Applies to:** `backend/`, `frontend/`, and the `xpoint-cfi` companion library
- **Resolves:** #730 (M0.1, part of the web reader epic #729)
- **Ground truth verified:** 2026-09-06

## Context

The web reader epic (#729) wants three things: read a book in the browser via
Thorium Web / Readium, jump from a highlight to its place in the book, and
create highlights and reading progress in the browser that KOReader also sees.
The third is what makes this a decision rather than an integration task — two
readers have to agree on where a passage is.

Today there is only one answer to "where is this". Highlights are created by the
KOReader sync alone and carry an `XPointRange`
(`domain/common/value_objects/xpoint.py`); chapters carry `start_xpoint` /
`end_xpoint`; reading progress is derived from the latest reading session's
`end_position`, itself an xpoint resolved to a `Position` through
`PositionIndex`. The **KOReader xpointer** is therefore not one of several
position formats in the system — it is the only one, and every reading feature
already built stands on it.

Readium does not speak it. What Readium speaks (verified 2026-09-06):

- **`@edrlab/thorium-web` 1.6.0** is an npm package (`StatefulReader`,
  `usePublication`, `plugins`, `positionStorage`) with a React 19 peer, matching
  the frontend. It ships **no highlight UI**: `textSelected` is a no-op and
  nothing calls `applyDecorations`. Everything about highlights is ours to
  build.
- **`@readium/navigator`** resolves a locator by **CSS selector plus text
  quote** — `text.before` / `text.highlight` / `text.after`, Hypothesis-style
  anchoring — scoped to a resource `href`. There is **no CFI support anywhere in
  the TS toolkit**.

And the conversion already exists, or nearly. The companion library
**xpoint-cfi** (separate repo, `~/Code/crossbill/xpoint-cfi`) parses an EPUB and
converts KOReader xpointers; it passes **763/763 corpus highlights across 13
books**, including an independent JS resolver, so the hard part — agreeing with
KOReader's own idea of document order and character offsets — is done and
measured. What it does not yet have is **Readium-locator output**; that is
M0.2 (#731).

So the question this ADR settles is not "which format" but **which format is
authoritative, and what is merely computed from it** — because the answer
decides what a highlight row stores, what breaks when an EPUB file is replaced,
and whether the browser or the e-reader wins when they disagree.

## Decision

**The KOReader xpointer stays the canonical stored position. Everything the web
reader needs is derived from it.**

### 1. Canonical: the xpointer

Highlight positions (`Highlight.xpoints`), reading-session boundaries, and
chapter boundaries continue to be stored as KOReader xpointers, unchanged. The
web reader adds no column to any of them and changes no sync contract.

The reason is round-trip fidelity, not sentiment. KOReader is the only client
that *writes* positions today and it writes xpointers; storing anything else
would mean converting on the ingest path, where a conversion failure loses the
user's highlight. Deriving instead means a conversion failure loses a *view* of
a highlight that is still safely stored.

### 2. Derived: the Readium locator

A **Locator** is `href` + `cssSelector` + `text.before` / `text.highlight` /
`text.after` (plus a `progression` estimate within the resource). It is computed
for the web reader from the stored xpointer and the EPUB file. It is **never the
source of truth**, is never the thing another feature reads to answer "where is
this highlight", and a stored locator — if measurements ever force us to persist
one (see §4) — is a cache entry, not a record.

The reverse direction exists too: a selection made in the browser produces a
locator, which is converted **to an `XPointRange`** before anything is written.
The write path stores xpointers whichever reader the reader used.

**Ground truth corrected, 2026-09-07 (M2.1/#740, M2.2/#741).** The note in
*Context* above — that everything about highlights is ours to build — is right
about **thorium-web** and wrong about the toolkit underneath it. The Readium TS
toolkit **does** ship a decoration layer: `EpubNavigator.applyDecorations(list,
group)` and `registerDecorationObserver(group, observer)` are public API on the
navigator, `@readium/decorator` supplies the styles and the diffing, and the
decorator module is injected into every publication frame. `@edrlab/thorium-web`
simply never calls any of it. What is ours to build is therefore the
*conversion* (xpointer → locator) and the *UI around a selection*, not the
drawing: rendering a highlight is one call on a navigator we own, under a group
name we reserve (`crossbill-highlights`,
`frontend/src/components/reader/decorations.ts`). This narrows M3.2 rather than
changing any decision above — the locator stays derived, and the decoration is
drawn from it.

### 3. CFI is export only

EPUB CFI is a **nice-to-have export format (M5.5), never stored and never on a
read path**. The Readium TS toolkit cannot consume it, so it buys nothing
in-app; its only value is interchange with tools outside Crossbill. If it is
built, it is generated on request from the canonical xpointer like any other
derived form.

### 4. Derivation is on demand, with a per-book cache

Anchors are converted **at request time**, from the EPUB, with the parsed
publication held in a per-book cache keyed by the book's EPUB file so that
converting a whole book's highlights parses once (#732). Nothing is persisted.

Persisting derived anchors is a **contingent** decision, not a rejected one.
M3.1 (#745) measures conversion time for the largest book in the prod clone; if
it exceeds roughly **200 ms per book**, a follow-up adds persistence and this
ADR gets an amendment. Persistence is deferred rather than adopted because a
persisted anchor is a second copy of a position that can silently disagree with
the first, and that cost is only worth paying against a measured number.

### 5. Every derived anchor is verified

A conversion is not trusted because it returned. **The text the derived anchor
resolves to is compared against the stored highlight text**, and the conversion
reports a match confidence so that **callers can reject weak matches** rather
than render a highlight in the wrong paragraph. `xpoint-cfi`'s existing
`normalize_for_comparison` is the comparison, and `before` / `after` are what
disambiguate a repeated phrase.

This is what makes the derived layer safe to be lossy. An EPUB replaced with a
differently-typeset edition does not corrupt anything — the stored xpointer is
untouched, and the anchors derived against the new file simply fail
verification, which is a visible, per-highlight "cannot locate this" rather than
a confident jump to the wrong place.

### 6. Backend placement: a new `web_reader` module

**All web-reader-specific backend surface lives in a new `web_reader` module** —
its own `domain/web_reader/`, `application/web_reader/`, and
`infrastructure/web_reader/`. That covers the anchor-conversion port and its
`xpoint-cfi` adapter, and the publication-serving and reader APIs that follow in
M1 and M2.

This was **decided by the maintainer on 2026-09-07 and supersedes the
`application/reading/protocols/` placement written in the body of #732**; that
issue's wording is the older plan, and this ADR is the one to follow.

The rationale is scope. The web reader is a distinct capability with its own
ports and its own read models — serving publication resources, positions,
locator views — none of which any existing reading feature needs. Folding it
into `reading` would grow that module's surface with an entire second
capability, when what `reading` is for is reading sessions, progress, and the
highlights the sync brings in. Keeping the two apart is also what keeps the
dependency honest: `web_reader` derives *from* the canonical positions
`reading` and `library` own, and nothing in `reading` depends on the web reader
existing.

Mechanically, adding the module means **listing `src.domain.web_reader` in the
`domain-module-independence` contract** in `backend/pyproject.toml` (CLAUDE.md
requires this for every new domain module). The other contracts need no edits:
`queries-are-dead-ends` and `application-no-infra` are wildcard or
layer-scoped and cover a new module for free.

One thing to note against precedent: ADR-0002 gave `semantic` no `domain/`
module at all, on the grounds that an embedding row has no invariants worth a
module. `web_reader` is deliberately getting the full set. If, once M0.3 and M1
land, `domain/web_reader/` turns out to hold nothing but pass-through types,
that is a signal to revisit — collapsing to an application/infrastructure-only
slice later is a smaller change than splitting a module out of `reading` would
have been.

## Alternatives considered

- **Store the locator as the canonical position.** Rejected: the only writer
  today is the KOReader sync, so this moves conversion onto the ingest path,
  where failure loses data rather than losing a view. It also makes the
  canonical position depend on the EPUB file we happen to hold — a locator's
  `cssSelector` is meaningless against a different edition, whereas the xpointer
  is the string KOReader itself will send back.
- **Store both, canonically.** Rejected: two writable positions for one
  highlight is two sources of truth, with no rule for which wins when they
  drift.
- **Adopt CFI as the interchange format between the two readers.** Rejected on
  the ground truth: `@readium/navigator` has no CFI support, so CFI would have
  to be converted to a locator anyway — a second derived hop that buys nothing
  the direct xpointer → locator conversion does not already give us.
- **Persist derived anchors from the start.** Rejected for now; see §4. It is
  a measurement away from being reconsidered, not a closed door.
- **Put the anchor port in `application/reading/protocols/`** (as #732's body
  says). Superseded by §6.

## Explicitly NOT adopted

- **Storing anything on `highlights` for the web reader.** No `locator` column,
  no `cfi` column. M3.1 adds `locator` to the highlight **view DTOs** behind a
  query flag — a read model, which ADR-0001 already sanctions.
- **A migration of existing positions.** Nothing is rewritten; 763/763 corpus
  highlights convert as they stand.
- **Trusting a conversion without verification**, even for the reverse
  direction. A browser selection that converts to an xpointer whose text does
  not match what the reader selected is a failed write, not a stored guess.
- **Changing the KOReader sync contract.** The plugin-only surface stays as it
  is, so no `koreader-plugin` minimum bump comes out of this ADR.

## Pending

**Nothing.** Both decisions this section held are settled below — auth for
iframe resource loads in *Amendment 1* (#737), and how web reading maps onto
reading sessions in *Amendment 3* (#742). A new question about anchors belongs
here as a new amendment; there is no open one to wait for.

## Consequences

**Good**

- One canonical position format, unchanged, across both readers. A highlight
  made in the browser is the same kind of thing as a highlight made on the
  e-reader, and the sync needs no new case.
- Every existing reading feature — progress, statistics, chapter attribution,
  the highlight views — keeps working with no migration, because none of them
  learn about locators.
- The derived layer is disposable. A bug in locator generation is a bad render,
  fixed by deploying a fix; it cannot corrupt stored data, and there is no
  backfill to redo.
- Verification turns the hardest failure mode — an EPUB file replaced with a
  different edition — into a visible per-highlight failure instead of a silent
  wrong jump.
- `web_reader` keeps an entire capability's ports, read models and APIs out of
  `reading`, and the dependency runs one way only.

**Costs**

- **On-demand derivation pays EPUB parsing at request time.** The per-book cache
  amortises it across a book's highlights, but a cold cache on a large book is
  latency inside a user request. This is the one cost with a number attached to
  it and a scheduled measurement (#745).
- **The cache needs invalidating on EPUB replace**, and getting that wrong
  produces anchors derived against a file that is no longer there — the failure
  verification is meant to catch, but noisily.
- **Two representations to reason about.** A reader-facing bug now has one more
  question in it: is the stored xpointer wrong, or the anchor derived from it?
  Verification is what keeps that question answerable.
- **A backend dependency on a git-pinned companion library.** `xpoint-cfi` is
  pinned to a tag (#732); a fix there is a two-repo change.
- **A new module to keep honest.** `web_reader` adds a name to the
  `domain-module-independence` contract and a module set that must not start
  reaching into `reading`'s internals as the epic grows.

**Open, tracked elsewhere**

- **#731 (M0.2)** — `xpoint-cfi` has no locator output yet. Until it lands,
  nothing in this ADR's §2 is implementable.
- **#745 (M3.1)** — the measurement that decides §4.

## Amendment 1: authentication for iframe resource loads

- **Date:** 2026-09-07
- **Resolves:** #737 (M1.4), the first of the two decisions left *Pending* above

`@readium/navigator` loads each resource of a publication straight into an
iframe. An iframe load is a plain browser request: it carries cookies and
nothing else, and in particular it cannot carry the SPA's access token, which is
held in memory precisely so that nothing else can reach it. Some second
credential is therefore unavoidable; the decision is which.

### A short-lived publication cookie, scoped to one book

`POST /api/v1/readium/books/{book_id}/session` is **Bearer-authenticated**,
checks that the book is the caller's (404 if it is not, as everywhere else in
the library), and sets an httpOnly cookie carrying a signed token that binds
**one user, one book, and an expiry**. It answers 200 with `{"expires_in": …}`
rather than 204: the cookie is httpOnly, so the page cannot read when it dies,
and it has to know in order to re-post before it does.

- **Signing** is the identity module's own — a JWT, HS256, `SECRET_KEY` — with a
  `type: "publication"` claim. Because that key also signs access tokens,
  `verify_access_token` was tightened in the same change to require
  `type == "access"` rather than merely *not* `refresh`: a narrower credential
  must not be spendable as a wider one.
- **Scope** is the cookie's `path`, `/api/v1/readium/books/{book_id}/`, built
  from the *parsed* id. Non-canonical spellings of the same id — `/books/01`,
  `/books/%31`, `/books/+1`, all of which FastAPI parses alike — therefore get
  a cookie scoped to the canonical path, which a browser will not send back to
  the URL the reader used. That is an **accepted sharp edge**: the cookie can
  only come out narrower than the request, never broader, so the failure mode
  is 401s on resource loads rather than a cookie reaching a book it does not
  name, and nothing we ship builds those URLs (the SPA and the generated client
  both interpolate an integer). Canonicalising defensively would mean taking
  `book_id` as a string on every publication route and rejecting what FastAPI
  accepts everywhere else in the API. A
  browser then sends it to that book's manifest, resources and position list,
  and offers it to no other book and to nothing else in the API. The server does
  not take the browser's word for it: the token's `book` claim is compared
  against the path's `book_id`, and a mismatch is **401** — the caller has
  presented no valid credential *for this book*, and 404 would mean telling a
  token scoped to book A whether book B exists.
- **Flags** are the refresh cookie's, for the same reasons: `httpOnly`,
  `Secure` unless `COOKIE_SECURE` says otherwise (which is what lets a
  plain-http development server work), `SameSite=Strict` — the reader and the
  API are the same site, so the navigator's own iframe loads carry it while
  nothing off-site can make a browser spend it.
- **TTL** is the access token's lifetime (`ACCESS_TOKEN_EXPIRE_MINUTES`, 15
  minutes by default) **as a ceiling, capped by what is left of the access
  token actually being spent** — `exp` of the cookie is the earlier of the two,
  and `Max-Age` and the `expires_in` in the body are that real number rather
  than the TTL. The cap is the point, not a detail: nothing revokes a
  publication token once signed, so a Bearer token with a minute left that
  bought a fresh quarter of an hour would be exactly the hole this TTL is
  supposed to close — a session that has ended (password changed, refresh
  family revoked) buying itself more reading on the way out. The route
  therefore authenticates through `get_authenticated_caller`, which carries the
  access token's `exp` alongside the user rather than decoding the token a
  second time. The reader re-posts on the schedule it already refreshes on;
  shorter buys nothing, since everything this cookie opens is already open to
  the token that minted it.
- **Every web reader route takes it**, the manifest included, because they share
  one dependency (`get_publication_reader`, built for this in M1.2). This widens
  nothing: a cookie is only ever issued to a caller that proved possession of a
  Bearer token for that same book, so it opens no door its holder could not
  already open — and one credential rule with one place to get wrong is the
  point of that dependency.

It is deliberately **not a session**: nothing is stored, nothing is revoked, and
a token is a pure function of its claims. What bounds it is its scope — one
book, read-only, for no longer than the token that bought it.

### Rejected: signed URLs

Signing each resource URL is equally stateless and needs no cookie at all. It
was rejected because the credential then travels **in the URL**: it lands in
access logs, in proxy logs and in browser history, and — since the navigator
gets its resource URLs from the manifest — it would have to be minted into **the
manifest itself**, which is a cached document. A cookie keeps the credential in
a header a log does not record, and lets the manifest stay the same document for
every request.

### Not adopted

- **Widening the cookie to the whole API.** It authenticates reading one
  publication; anything else is what the Bearer token is for.
- **A revocation list for publication tokens.** At a 15-minute TTL bounded by
  the access token's own, this would add a store and a lookup to buy back
  minutes.
- **Any change to the plugin surface.** The KOReader plugin does not load
  publications, so no `koreader-plugin` minimum bump comes out of this
  amendment either.

## Amendment 2: a publication's own scripts

- **Date:** 2026-09-07
- **Arises from:** #741 (M2.2), found in adversarial review of the reader route

*Amendment 1* settled how an iframe load authenticates. It did not ask what the
thing inside the iframe is allowed to do, and the answer turned out to be
"everything".

`@readium/navigator` frames each resource with
`sandbox="allow-same-origin allow-scripts"` (`FrameManager.ts:28`) and the
framed document is a `blob:` URL minted by the SPA — so the frame is
**same-origin with the app**. The CSP the library injects into that document
permits the content's own JavaScript outright:
`script-src ${domains} blob: 'unsafe-inline'` (`FrameBlobBuilder.ts:5-21`). A
`<script>` in an EPUB therefore ran with the reader's own privileges. This was
not theoretical: a test fixture's `onload` handler reached
`parent.document.body` and marked it.

That matters because **Crossbill's books are uploaded by their owner from
wherever they found them**. The library is not a trust boundary, and a
downloaded EPUB is closer to a downloaded web page than to a document.

**Decision: a publication's markup is disarmed before Readium ever frames it.**
The `Publication`'s fetcher is ours, and Readium builds every frame from what
that fetcher returns, so a wrapper around it (`publicationHardening.ts`) parses
each HTML/XHTML resource, removes `<script>` elements, `on*` handlers and
`javascript:` URLs, and prepends
`script-src blob:; object-src 'none'; child-src 'none'`. CSP policies combine
by intersection, so ours meets the library's at `blob:` — which is exactly the
line between Readium's own injected scripts and the book's, since the former
are injected as `<script src="blob:...">` (`Injector.ts`) and the latter never
are.

**Rejected: dropping `allow-scripts`.** Readium injects `css-selector-generator`
into every document (`epubInjectables.ts`), and that is what turns a browser
selection into a Locator — §2's write path, and the ground M3 and M4 stand on.
Removing script execution from the frame removes the anchors with it.

**Rejected: dropping `allow-same-origin`.** An opaque-origin frame cannot be
scripted by its parent at all, which is how the navigator drives it.

**Residual, accepted for now.** This is a mitigation, not a sandbox: the frame
is still same-origin, so anything that does get script running there has the
page. Scripted EPUB content does not work, which is the intended trade. The
architectural fix is to serve publication resources from a separate origin;
Readium's blob-URL design makes that awkward and it is not M2.2's to do.

**Residual closed at the source (#741 follow-up).** The part of that residual
that was about *documents loaded directly* rather than framed — a frame
navigating itself, or any path reaching a resource URL without going through the
hardening fetch — is now handled by the server: `GET
/api/v1/readium/books/{book_id}/resources/{path}` answers with
`Content-Security-Policy: sandbox` on both 200 and 304, which gives such a
document an opaque origin and no scripts whatever the frontend does, and costs
the reader nothing because the navigator reads the response as *text* and frames
a blob it builds itself (`FrameBlobBuilder.buildHtmlFrame`), so the header never
travels into the frame. `SecurityHeadersMiddleware` was changed in the same
place to leave a response's own policy alone rather than overwrite it, since the
app-wide policy is only sent outside development — exactly where this one
matters.

## Amendment 3: how web reading becomes reading sessions

- **Date:** 2026-09-07
- **Resolves:** #742 (M2.3), the second of the two decisions left *Pending*
  above — which is now empty

Reading progress is the `end_position` of the latest row in `reading_sessions`,
and the statistics page is `ReadingStatisticsCalculator` over every row of it.
Neither knows the web reader exists. So the question this amendment settles is
what the browser has to write for those two to keep being right.

### The reader writes real reading sessions

**Web reading produces ordinary `reading_sessions` rows** — the same table, the
same columns, the same meaning — rather than a parallel notion of progress that
the progress bar and the calculator would then have to learn about. Nothing in
`reading` changed: the calculator, the activity grid, the book-details view's
`reading_position` and the statistics endpoint were not touched, and a session
made in the browser shows up in all of them because it is not a special kind of
row.

A session is written by the position endpoint itself, on the request that
reports a position:

- **It starts on the first position write after the book is opened**, not on
  opening. The navigator announces where it is as soon as a frame loads, so
  "opened" is a moment the browser reports whether or not anybody reads
  anything; the frontend therefore remembers the position the book opened at
  and writes only once it *changes*. Opening a book and closing it again
  records nothing.
- **It grows on every write after that.** `end_time` becomes the moment
  reported, `end_position` becomes where the reader now is, and the xpoint
  range is extended to the furthest the session reached — `ReadingSession.
  extend_to`. A reader paging backwards moves `end_position` back with them,
  because that is where they are and that is what progress means; the range
  keeps its furthest extent, because a range that ran backwards would not be
  one.
- **It is kept alive while the reader is on one page.** Sitting still is not
  the same as having stopped, so the reader re-sends its position every ten
  minutes while the tab is visible; an unchanged position is still a position
  arriving, and extends the session like any other.
- **It ends by not being extended.** This is the part worth stating plainly:
  **nothing has to run to close a web reading session.** Its `end_time` is
  already the last position it was told about, so a session that stops being
  extended is over the moment it stops. There is no background job, no sweeper,
  and no idle-close write — and a tab left open all night adds no reading time,
  because no positions arrive while nobody reads.
- **A gap decides where one sitting is cut from the next.** A write arriving
  more than `WEB_READING_SESSION_IDLE_SECONDS` (default 30 minutes) after the
  open session's end starts a new session instead of extending it. Generous on
  purpose: since over-counting is structurally impossible, the timeout only
  decides *granularity*, and a slow reader on one page must not be cut in two.
- **Leaving the book closes it explicitly.** The frontend's last write carries
  `closing`, which clears the pointer to the open session so that the next
  sitting starts a fresh one however soon the reader comes back. Written with a
  `keepalive` fetch, the only kind of request a page may leave behind.

The session records `device_id = "crossbill-web-reader"`, which both keeps
browser reading distinguishable in the sessions list and keeps its content hash
from colliding with a KOReader session that happened to start at the same
instant.

**A session's pages are Readium position numbers.** `start_page` / `end_page`
have never been a canonical pagination — a KOReader session carries *that
device's* page numbers, which depend on its screen and its font — so the honest
equivalent for a browser session is the pagination the browser shows: the
position list this API serves, which the reader's own chrome counts "Page X of
N" from. The number arrives as `locations.position`, which is the browser
handing back an index into a document of ours rather than a claim about the
book, and a value outside Readium's 1-based list is treated as absent rather
than refused — the position itself is already stored, and a page range is what a
session is *labelled* with.

Leaving them null was not merely a blank line on a card. The activity grid
counts pages only when **every** session of a book has them
(`ActivityUnitRule.EVERY_SESSION_PAGED`), so one page-less web session silently
rewrote a KOReader-read book's whole year from pages into minutes — a
consequence no reader would connect to having opened the book in a browser. The
page range follows the same rule as the xpoint range: it keeps the furthest the
sitting reached, so paging back reports the ground covered rather than a range
running backwards, and a sitting the heartbeat carried across one page reports
that page at both ends instead of nothing.

### The new table is a cache and a bookmark, not a second source of truth

`web_reading_positions` (one row per reader and book) holds the Readium locator,
the xpointer it converted to, the resolved `Position`, when it was recorded, and
the id of the session still being extended.

**It is not where "how far through am I" is answered.** That stays the latest
session's `end_position`, exactly as before. What this table holds is the two
things a reading session cannot: the locator, so a browser can be put back
precisely where it was (M2.4), and the open-session pointer, so the next write
knows whether it is continuing a sitting. §2 already called a stored locator a
cache entry rather than a record, and that is what this is — if the EPUB is
replaced, the locator becomes a reference into a book that no longer exists and
the xpointer beside it is what still means something.

### Endpoints, and where they live

`GET` and `PUT /api/v1/readium/books/{book_id}/reading-position`.

**Under the `readium` prefix, not `/books/{id}/`** as #742's body wrote it. That
wording predates *Amendment 1*: the publication cookie is scoped by `path` to
`/api/v1/readium/books/{id}/`, so a route outside that prefix could not be
reached by the credential a reader holds when its access token has lapsed
mid-page. Putting these two inside it is what lets `get_publication_reader`
serve them like every other web reader route — one credential rule, one place to
get it wrong.

The `PUT` body is the locator as the navigator serializes it, plus
`recorded_at`, plus `closing`. `recorded_at` is the reader's own clock, and it
sets the *reading session's* moment only — never which of two writes is later;
see *Concurrency* below for both halves of that and for the bounds it is held
within. A write that has been overtaken is answered with what is stored rather
than refused: the debounced write and the one a closing tab sends race by
design, and the loser is not an error.

### A reading position usually has no quote at all

**Corrected 2026-09-07, from the maintainer's own reading.** The paragraph this
replaces assumed a reading position arrives with a text quote and a CSS
selector, "which scopes the search to one element and makes the match unique far
more often than not". It arrives with neither. `EpubNavigator` reports a page
turn in a reflowable book from its column snapper's `progress` event, whose
payload is a start fraction, an end fraction and some fragment ids; the Locator
it builds from that carries an `href`, a `position`, a `progression`, an empty
`fragments` array — and no text whatever. Every real position write was
therefore refused with *"no highlight and no context to anchor to"*, while every
test passed, because the fixtures were shaped like a **selection**.

So the conversion synthesises a quote out of the document itself when the
Locator brought none, from whatever it did bring, and hands it back through the
same tested conversion the quote path uses. `AnchorSource` records which of the
three it was:

- **`QUOTE`** — the Locator's own text. What a selection produces, and what
  M3/M4's highlights will be.
- **`ELEMENT`** — the element a `cssSelector` or a fragment id names; the quote
  is that element's first run of text, so the position lands where the element
  begins.
- **`PROGRESSION`** — the text at that fraction of the resource. What a page
  turn produces, and therefore the ordinary case rather than the exotic one.

### The confidence floor, one per kind of anchor

§5 requires callers to reject weak matches. The three anchors above are not
points on one scale, so there is a floor for each rather than one for all — a
`BOTH_CONTEXTS` from a quote and a `FUZZY` from a progression are not
comparable, and the grade a synthesised quote comes back with would otherwise
measure how well this code copied text out of a document it was reading anyway.
Each is therefore **capped** at what the Locator's own evidence was worth, and
compared against its own floor:

| Anchor | Ceiling | Floor | Because |
| --- | --- | --- | --- |
| `QUOTE` | `BOTH_CONTEXTS` | `HIGHLIGHT_ONLY` | Graded on evidence the caller supplied — §5's case exactly |
| `ELEMENT` | `HIGHLIGHT_ONLY` | `HIGHLIGHT_ONLY` | Names one place, corroborated by nothing else |
| `PROGRESSION` | `FUZZY` | `FUZZY` | Approximate by construction, and accepted anyway |

`HIGHLIGHT_ONLY` for a quote — the quote occurring exactly once — refuses
exactly the two grades that mean *we do not know which place this is*: `FUZZY`,
the quote not being in the book as written, which is the shape a replaced
edition takes, and `AMBIGUOUS`, the quote occurring several times with neither
context settling which. That is one grade below what a *highlight* will demand
(M4.1): a highlight drawn in the wrong paragraph is a visible, lasting falsehood
about what the reader marked, while a reading position that is off costs a
moment finding one's place.

**Accepting `PROGRESSION` is the load-bearing choice here**, and it is what the
live failure taught: a floor that refused an approximate anchor would refuse to
record reading at all, since almost every reading position *is* one. What still
refuses is the conversion failing outright — a Locator naming a resource the
book does not have — which is the signal §5 is actually for. A refusal is
**422**, not 400: the request is well formed and the caller could not have sent
anything better.

The alternative, asking the frontend for a richer Locator, was rejected on
inspection: the snapper's `progress` message has no text in it, `EpubNavigator`
exposes no way to ask a frame for one, and scraping the iframe's DOM for context
on every page turn is a great deal of machinery to make the *client* do work the
server can do against a publication it has already parsed.

### Concurrency: the position row is the control point

Two tabs of the same book write independently, and the first draft took a
decision between reading the row and writing it — which is a decision two
writers can both take. It also wrote the reading session *first*, so a losing
position write left a session row behind it.

**The position is claimed first, in one conditional upsert, and the session is
written only by the request that won the claim.** The write is an
`INSERT … ON CONFLICT (user_id, book_id) DO UPDATE … WHERE updated_at <
:written_at`, which answers both questions the write depends on — is there a row
yet, is this newer than what is in it — at the moment of writing. The
open-session pointer is then attached under `WHERE updated_at = :written_at`, so
only the writer that is still the latest may move it: a close cannot undo a page
turn that landed after it, and a page turn cannot reopen a session closed after
it. An overtaken write is answered with what is stored, because the write a
closing tab sends and the one a page turn sends race by design.

**`updated_at` is the server's clock**, and it is the only thing that decides
which of two writes is later. Ordering on the reader's own clock reads well
until a second device is five minutes slow, at which point every write it will
ever make is older than what is stored and is refused for good — a permanent,
silent failure to record anything, bought to tidy up a reordering that is
sub-second in practice. The reader's clock is used for the reading session's
arithmetic, where it is the honest source, and nowhere else; the session's end
time only ever moves forward, so a disagreeing clock cannot shorten a sitting.

That clock is **bounded at both ends**: never later than now, or a clock running
ahead invents reading time and then locks its owner out until the date it
claimed; and never earlier than one idle window ago, which is as far back as a
claim can reach and still join anything. Proportionate rather than airtight —
this is a self-hosted library where the only person who can spend a credential
is the person whose own statistics a lie would inflate.

**Residual, accepted.** Two genuinely simultaneous *first* writes for a book can
each create a session in the window between the two statements; the pointer ends
at the later writer's, and the other is a stray zero-second session. No 500, no
orphaned pointer, no duplicate row — one extra row in a rarely-hit race, which
is a great deal less than what it replaced.

### The caches are process-local, and the deployment is one process

`PublicationCaches` evicts by calling a method on objects held in memory, which
reaches this interpreter and no other. `Dockerfile` runs `uvicorn src.main:app`
with **no `--workers`**, and the upload that replaces an EPUB is served by the
same process that holds the caches, so today every cache that could go stale is
told.

This is a real constraint, not an implementation detail: give uvicorn a second
worker and a book replaced through worker A goes on being served from worker B's
parse until its LRU happens to drop it, with no error anywhere to say so. Adding
workers therefore means **replacing** this rather than adding to it — a shared
cache (Redis), or a cache key that changes when the bytes do (a content hash
rather than the filename, which makes eviction unnecessary altogether). Neither
is worth building for a deployment that has one process; both are a day's work
when it stops having one. The constraint is written down at
`PublicationCaches`, at the `Dockerfile` CMD, and here.

### The reader says it is still there

A session ends by not being extended, which means a reader who stays on one page
for half an hour ends theirs at their last page turn — and a reader who never
turns a page records nothing at all, since the position a book opens at is
deliberately not written. So the reader **re-sends its current position every
ten minutes while the tab is visible**, a third of the idle window, which the
server reads as the session continuing because an unchanged position is still a
position arriving. A hidden tab sends nothing, which is what keeps a book left
open overnight from recording a night's reading.

### Also decided here

- **The book's own `end_position` is backfilled on the way past.** Progress is a
  fraction of it, and until now only the KOReader upload path ever measured a
  book's length — so a book read only in the browser had no denominator and no
  progress. Reading one in the browser is as good an occasion to learn how long
  it is.
- **A second per-book cache, evicted with the first.** Resolving an xpointer to
  a `Position` means a whole-EPUB parse, and the reader asks every few seconds,
  so `CachedBookPositionIndex` holds position indices exactly as the anchor
  service holds parsed publications. Both key on `Book.ebook_file`, which is
  reused when an EPUB is replaced, so the upload path now evicts through a
  `PublicationCaches` fan-out rather than naming one of them — one dependency,
  however many caches grow behind it.

### Not adopted

- **A background job to close idle sessions.** There is nothing to close: see
  above. A sweeper would exist only to write an `end_time` that is already
  correct.
- **Ordering two writes by the reader's clock.** See *Concurrency* above: it
  trades a sub-second reordering for a device with a slow clock never recording
  anything again.
- **Scraping the publication frame for text context** so that every Locator
  carries a quote. The server already holds the parsed publication; the client
  would be doing the same work worse, on every page turn.
- **A `web_reading_progress` notion of its own**, read by the progress bar
  instead of sessions. It would be a second answer to a question that already
  has one, and every reader of progress would have to learn to ask both.
- **Trusting the client's clock for durations, or for ordering.** It sets the
  moment a session is measured from, bounded at both ends; which of two writes
  is later is the server's own clock and nothing else.
- **Writing a position on open.** It would start a session for opening a book,
  and — once M2.4 resumes into a stored position — write back the position it
  had just restored.
- **Any change to the plugin surface.** KOReader still uploads finished
  sessions the way it always has, so no `koreader-plugin` minimum bump comes out
  of this amendment either.
