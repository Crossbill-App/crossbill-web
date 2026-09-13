# ADR-0004: Position anchors for the web reader

- **Status:** Accepted
- **Date:** 2026-09-07
- **Amended:** 2026-09-13 — *Amendment 6* reverses §4
- **Applies to:** `backend/`, `frontend/`, and the `xpoint-cfi` library
- **Resolves:** #730 (M0.1, part of the web reader epic #729)
- **Ground truth verified:** 2026-09-06

## Context

The web reader epic (#729) wants three things: read a book in the browser via
Thorium Web / Readium, jump from a highlight to its place in the book, and
create highlights and reading progress in the browser that KOReader also sees.
The third makes this a decision rather than an integration task — two readers
have to agree on where a passage is.

Today there is only one answer to "where is this". Highlights are created by the
KOReader sync alone and carry an `XPointRange`
(`domain/common/value_objects/xpoint.py`); chapters carry `start_xpoint` /
`end_xpoint`; reading progress is the latest session's `end_position`, itself an
xpoint resolved to a `Position` through `PositionIndex`. The **KOReader
xpointer** is therefore not one of several position formats in the system — it
is the only one, and every reading feature already built stands on it.

Readium does not speak it. What Readium speaks (verified 2026-09-06):

- **`@edrlab/thorium-web` 1.6.0** is an npm package with a React 19 peer,
  matching the frontend. It ships **no highlight UI**: `textSelected` is a no-op
  and nothing calls `applyDecorations`. Everything about highlights is ours to
  build.
- **`@readium/navigator`** resolves a locator by **CSS selector plus text
  quote** — `text.before` / `text.highlight` / `text.after`, Hypothesis-style
  anchoring — scoped to a resource `href`, and has **no CFI support**.

And the conversion already exists. The companion library **xpoint-cfi**
(separate repo, `~/Code/crossbill/xpoint-cfi`) parses an EPUB and converts
KOReader xpointers; it passes **763/763 corpus highlights across 13 books**,
including an independent JS resolver, so the hard part — agreeing with
KOReader's own idea of document order and character offsets — is done and
measured. Readium-locator output was the one thing missing when this was
written, and landed in #731 (M0.2).

So the question this ADR settles is not "which format" but **which format is
authoritative, and what is merely computed from it** — the answer decides what a
highlight row stores, what breaks when an EPUB is replaced, and whether the
browser or the e-reader wins when they disagree.

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
user's highlight. Deriving means it loses a *view* of one still safely stored.

> **Amended by *Amendment 6*.** The xpointer is still canonical. "The web reader
> adds no column" is not: R4.2 (#839) adds a derived locator column beside it,
> on the same terms as `position`.

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

> **Amended by *Amendment 6*.** A stored locator is now a derived column with a
> source hash rather than a cache entry. Everything else stands, the reverse
> direction included.

**Ground truth corrected, 2026-09-07 (M2.1/#740, M2.2/#741).** The note in
*Context* above — that everything about highlights is ours to build — is right
about **thorium-web** and wrong about the toolkit underneath it. The Readium TS
toolkit **does** ship a decoration layer: `EpubNavigator.applyDecorations` and
`registerDecorationObserver` are public API on the navigator, the
`@readium/decorator` module supplies the styles and the diffing, and it is
injected into every publication frame; `@edrlab/thorium-web` simply never calls
any of it. What is ours to build is therefore the *conversion* and the *UI
around a selection*, not the drawing — rendering a highlight is one call on a
navigator we own, under a group name we reserve (`crossbill-highlights`). This
narrows the drawing work in R4.5 (#831) rather than changing any decision
above.

### 3. CFI is export only

EPUB CFI is a **nice-to-have export format, never stored and never on a read
path**. The Readium TS toolkit cannot consume it, so it buys nothing in-app; its
only value is interchange with tools outside Crossbill; it is tracked as a
nice-to-have in #760 (M5.5) and nothing depends on it. If it is ever built, it
is generated on request from the canonical xpointer like any other derived
form.

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

**Measured, 2026-09-08 — see *Amendment 5*.** The threshold was exceeded (561 ms
worst book), and persistence was still not adopted: the cost turned out to be a
quadratic selector generator in `xpoint-cfi` rather than anything this cache or
a persisted anchor addresses.

> **Reversed by *Amendment 6* (2026-09-13).** Locators are derived at ingest and
> stored in a column; no read path derives one. Read that amendment before
> acting on anything in this section.

### 5. Every derived anchor is verified

A conversion is not trusted because it returned. **The text the derived anchor
resolves to is compared against the stored highlight text**, and the conversion
reports a match confidence so **callers can reject weak matches** rather than
render a highlight in the wrong paragraph. `normalize_for_comparison` is the
comparison; `before` / `after` disambiguate a repeated phrase.

This is what makes the derived layer safe to be lossy. An EPUB replaced with a
differently-typeset edition corrupts nothing — the stored xpointer is untouched,
and anchors derived against the new file simply fail verification, a visible
per-highlight "cannot locate this" rather than a confident jump to the wrong
place.

### 6. Backend placement: a new `web_reader` module

**All web-reader-specific backend surface lives in a new `web_reader` module** —
its own `domain/web_reader/`, `application/web_reader/` and
`infrastructure/web_reader/`, covering the anchor-conversion port and its
`xpoint-cfi` adapter as well as the publication-serving and reader APIs.

This was **decided by the maintainer on 2026-09-07 and supersedes the
`application/reading/protocols/` placement written in the body of #732**, whose
wording is the older plan.

The rationale is scope. The web reader is a distinct capability with its own
ports and read models — serving publication resources, positions, locator
views — none of which any existing reading feature needs. Folding it into
`reading` would grow that module with a whole second capability, when what
`reading` is for is sessions, progress, and the highlights the sync brings in.
Keeping the two apart also keeps the dependency honest: `web_reader` derives
*from* the canonical positions `reading` and `library` own, and nothing in
`reading` depends on the web reader existing.

Mechanically, adding the module means **listing `src.domain.web_reader` in the
`domain-module-independence` contract** in `backend/pyproject.toml`, as
CLAUDE.md requires for every new domain module. The other contracts need no
edits: `queries-are-dead-ends` and `application-no-infra` are wildcard or
layer-scoped, and cover a new module for free.

One thing to note against precedent: ADR-0002 gave `semantic` no `domain/`
module at all, on the grounds that an embedding row has no invariants worth a
module. `web_reader` is deliberately getting the full set. **The signal this
section watches for has half fired**: with R1 (#792) and R3 (#823) built,
`domain/web_reader/` holds `exceptions.py` and nothing else. Revisit once epic
#827 is done, not before — collapsing to an application/infrastructure-only
slice later is a smaller change than splitting a module out of `reading` would
have been.

## Alternatives considered

- **Store the locator as the canonical position.** Rejected: it makes the
  canonical position depend on the EPUB file we happen to hold — a locator's
  `cssSelector` is meaningless against a different edition, whereas the xpointer
  is the string KOReader itself will send back. The only writer today is the
  KOReader sync, so this moves conversion onto the ingest path, where failure
  loses data rather than losing a view. (*Amendment 6* is where that premise
  expired: the browser became a writer too.)
- **Store both, canonically.** Rejected: two writable positions for one
  highlight is two sources of truth, with no rule for which wins when they
  drift. Still rejected after *Amendment 6*: a derived column with a source hash
  is not a second canonical position, and the rule for which wins is that the
  xpointer does.
- **Adopt CFI as the interchange format between the two readers.** Rejected on
  the ground truth: `@readium/navigator` has no CFI support, so CFI would be
  converted to a locator anyway — a second derived hop that buys nothing.
- **Persist derived anchors from the start.** Rejected for now; see §4.
  **Adopted 2026-09-13 — see *Amendment 6***, on grounds §4 did not weigh.
- **Put the anchor port in `application/reading/protocols/`** (as #732's body
  says). Superseded by §6.

## Explicitly NOT adopted

- **Storing anything on `highlights` for the web reader.** No `locator` column,
  no `cfi` column; a locator reaches a view through the highlight **view DTOs**
  behind a query flag — a read model, which ADR-0001 already sanctions.
  **Reversed by *Amendment 6*:** R4.2 (#839) adds a locator column and its
  source hash to `highlights` and `reading_sessions`. No `cfi` column, still.
- **A migration of existing positions.** Nothing is rewritten; 763/763 corpus
  highlights convert as they stand, and *Amendment 6*'s new columns are
  backfilled from xpointers it does not touch.
- **Trusting a conversion without verification**, even for the reverse
  direction. A browser selection converting to an xpointer whose text does not
  match what the reader selected is a failed write, not a stored guess.
  *Amendment 6* reopens what that should cost the reader, not the verification.
- **Changing the KOReader sync contract.** The plugin-only surface stays as it
  is, so no `koreader-plugin` minimum bump comes out of this ADR.

## Pending

**One question, opened by *Amendment 6*** — whether a reverse conversion that
fails verification should stay a rejected write — is stated with its
alternatives and its deadline in that amendment's *Open* section. Nothing else
is open.

## Consequences

**Good**

- One canonical position format, unchanged, across both readers. A highlight
  made in the browser is the same kind of thing as one made on the e-reader, and
  the sync needs no new case.
- Every existing reading feature — progress, statistics, chapter attribution,
  the highlight views — keeps working with no migration, because none of them
  learns about locators.
- The derived layer cannot corrupt the canonical one. A bug in locator
  generation is a bad render or a bad column; the stored xpointer it was
  computed from is untouched, so the fix is a deploy and a backfill rather than
  a data-recovery exercise. (*Revised under Amendment 6*: there is now a
  backfill to redo, where before there was nothing.)
- Verification turns the hardest failure mode — an EPUB file replaced with a
  different edition — into a visible per-highlight failure instead of a silent
  wrong jump.
- `web_reader` keeps an entire capability's ports, read models and APIs out of
  `reading`, and the dependency runs one way only.

**Costs**

*Revised 2026-09-13 under Amendment 6. The two costs this list opened with —
EPUB parsing inside a user request, and invalidating a parsed-publication cache
on replace — are gone with the design that incurred them.*

- **Conversion cost moves onto ingest.** Sync and EPUB upload now pay it, for
  every row of a book rather than the rows a view renders. That is the right
  place — those paths are already slow and already parse the EPUB — but it is a
  real cost on a path a user waits on, and `Crossbill-App/xpoint-cfi#3` still
  decides how large.
- **A stored locator can be stale**, and something has to say so:
  `locator_source_hash` per row, checked on every read, plus a backfill on EPUB
  upload — one more invariant, in exchange for the cache invalidation it
  replaces.
- **A row can be unplaceable, and callers must render that.** A null or stale
  locator is answered as "cannot place this" rather than recomputed, so every
  read path drawing one needs the empty case.
- **Two representations to reason about.** A reader-facing bug now has one more
  question in it: is the stored xpointer wrong, or the locator derived from it?
  Verification and the source hash are what keep that question answerable.
- **A backend dependency on a git-pinned companion library.** `xpoint-cfi` is
  pinned to a tag (#732); a fix there is a two-repo change.
- **A new module to keep honest.** `web_reader` adds a name to the
  `domain-module-independence` contract and a module set that must not start
  reaching into `reading`'s internals as the epic grows.

**Open, tracked elsewhere**

- ~~**#731 (M0.2)** — `xpoint-cfi` has no locator output yet.~~ Landed.
- ~~**#745 (M3.1)** — the measurement that decides §4.~~ Made; see
  *Amendment 5*. It left open **Crossbill-App/xpoint-cfi#3**, the quadratic
  selector generation it found. *Amendment 6* moves that cost off the read path
  without removing it: it is paid at sync and at EPUB upload, where R4.2 (#839)
  meets it.

## Amendment 1: authentication for iframe resource loads

- **Date:** 2026-09-07
- **Resolves:** #737 (M1.4), the first of the two decisions left *Pending* above
- **Rebuilt by R1:** #800 (the token and the session route), #801 (cookie-only
  auth on the manifest, positions and resources)

Some second credential beside the SPA's access token is unavoidable, because the
access token is held in memory precisely so that nothing else can reach it. The
decision is which.

### What actually cannot carry a header

*Corrected 2026-09-13, against what R1 built.* This amendment originally argued
from "an iframe load is a plain browser request: it carries cookies and nothing
else" — the right conclusion from the wrong mechanism, and the mechanism decides
which routes need the cookie.

Readium never loads a chapter over the network into a frame. It reads the
resource as *text* through a fetcher the app supplies and builds a same-origin
`blob:` document from it (`ReadiumReader.publicationFrom`; see also *Amendment
2*, which turns on the same fact), so the manifest, the position list and every
chapter arrive through the app's own `fetch` — which could carry an
`Authorization` header if we wanted it to. What cannot is everything the *framed
document* then asks for on its own: images, stylesheets and fonts, resolved by
the browser against the `<base href>` Readium injects, with no JavaScript of
ours in the path. In an illustrated or webfonted book those are most of the
requests.

R1 therefore made **every** publication route cookie-only rather than mixing
credentials by route: `get_publication_reader`
(`infrastructure/web_reader/dependencies.py`) takes the cookie alone on the
manifest, the position list and the resources, and the Bearer token is spent
exactly once, on `POST .../session`, to mint it. One credential per route, and
it is the one a chapter's own images are able to present.

### A short-lived publication cookie, scoped to one book

`POST /api/v1/readium/books/{book_id}/session` is **Bearer-authenticated**,
checks that the book is the caller's (404 if it is not, as everywhere else in
the library), and sets an httpOnly cookie carrying a signed token that binds
**one user, one book, and an expiry**. It answers 200 with `{"expires_in": …}`
rather than 204: the cookie is httpOnly, so the page cannot read when it dies,
and it has to know in order to re-post before it does.

- **Signing** is a JWT, HS256, under `PUBLICATION_TOKEN_SECRET_KEY` falling back
  to `SECRET_KEY`, with a `type: "publication"` claim. Because that fallback key
  also signs access tokens, `verify_access_token` was tightened to require
  `type == "access"` rather than merely *not* `refresh`: a narrower credential
  must not be spendable as a wider one.
- **Scope** is the cookie's `path`, `/api/v1/readium/books/{book_id}/`, built
  from the *parsed* id. A browser sends it to that book's manifest, resources
  and position list, and offers it to no other book and to nothing else in the
  API. The server does not take the browser's word for it: the token's `book`
  claim is compared against the path's `book_id`, and a mismatch is **401** —
  the caller has presented no valid credential *for this book*, and 404 would
  mean telling a token scoped to book A whether book B exists.

  Non-canonical spellings of the same id — `/books/01`, `/books/%31`,
  `/books/+1`, all of which FastAPI parses alike — therefore get a cookie scoped
  to the canonical path, which a browser will not send back to the URL the
  reader used. An **accepted sharp edge**: canonicalising defensively would mean
  taking `book_id` as a string on every publication route, and the cookie can
  only come out narrower than the request, never broader, so the failure mode is
  401s rather than a cookie reaching a book it does not name, and nothing we
  ship builds one.
- **Flags** are the refresh cookie's, for the same reasons: `httpOnly`,
  `Secure` unless `COOKIE_SECURE` says otherwise (which is what lets a
  plain-http development server work), `SameSite=Strict` — the reader and the
  API are the same site, so the navigator's own loads carry it while nothing
  off-site can make a browser spend it.
- **TTL** is the publication token's own lifetime **as a ceiling, capped by what
  is left of the access token actually being spent** — the cookie's `exp` is the
  earlier of the two, and `Max-Age` and `expires_in` are that real number. The
  cap is the point: nothing revokes a publication token once signed, so a Bearer
  token with a minute left that bought a fresh quarter of an hour would be
  exactly the hole this TTL closes — a session that has ended (password changed,
  refresh family revoked) buying itself more reading on the way out. The route
  authenticates through `get_authenticated_caller`, which carries the access
  token's `exp` alongside the user; the reader re-posts on the schedule it
  already refreshes on (`useReaderSession`).
- **Every publication route takes it**, the manifest included, because they
  share one dependency. This widens nothing: a cookie is only ever issued to a
  caller that proved possession of a Bearer token for that same book, so it
  opens no door its holder could not already open — and one credential rule with
  one place to get wrong is the point of that dependency.

  **The read routes, and only those.** R4's non-publication routes take the
  Bearer token instead: the highlight-locator reads (#829) sit outside the
  prefix, and the reading-position routes (#830) keep it but decline the cookie
  dependency. Either way the cookie opens no write, which keeps the cookie
  read-only by construction: a credential a book's own markup can make the
  browser spend must not write.

It is deliberately **not a session**: nothing is stored, nothing is revoked, and
a token is a pure function of its claims. Its scope is what bounds it — one
book, read-only, for no longer than the token that bought it.

### Rejected: signed URLs

Signing each resource URL is equally stateless and needs no cookie at all. It
was rejected because the credential then travels **in the URL**: it lands in
access logs, proxy logs and browser history, and — since the navigator gets its
resource URLs from the manifest — it would have to be minted into **the manifest
itself**, which is a cached document. A cookie keeps the credential in a header
a log does not record, and lets the manifest stay one document for everyone.

### Not adopted

- **Widening the cookie to the whole API.** It authenticates reading one
  publication; anything else is what the Bearer token is for.
- **A revocation list for publication tokens.** At a TTL bounded by the access
  token's own, this adds a store and a lookup to buy back minutes.
- **Any change to the plugin surface.** The plugin does not load publications,
  so no `koreader-plugin` minimum bump comes out of this amendment either.

## Amendment 2: a publication's own scripts

- **Date:** 2026-09-07
- **Arises from:** #741 (M2.2), found in adversarial review of the reader route

*Amendment 1* settled how a publication resource authenticates. It did not ask
what the thing inside the frame may do, and the answer was "everything".

`@readium/navigator` frames each resource with
`sandbox="allow-same-origin allow-scripts"` (`FrameManager.ts`) and the framed
document is a `blob:` URL minted by the SPA, so the frame is **same-origin with
the app**; the CSP the library injects permits the content's own JavaScript
outright (`script-src ${domains} blob: 'unsafe-inline'`, `FrameBlobBuilder.ts`).
A `<script>` in an EPUB therefore ran with the reader's own privileges — not
theoretically: a test fixture's `onload` handler reached `parent.document.body`
and marked it.

That matters because **Crossbill's books are uploaded by their owner from
wherever they found them**: the library is not a trust boundary, and a
downloaded EPUB is closer to a downloaded web page than to a document.

**Decision: a publication's markup is disarmed before Readium ever frames it.**
The `Publication`'s fetcher is ours and Readium builds every frame from what it
returns, so a wrapper around it
(`frontend/src/components/reader/sanitizeResponse.ts`) parses each HTML/XHTML
resource, removes `<script>` elements, `on*` handlers, `javascript:` URLs and
`<meta http-equiv="refresh">`, and prepends
`script-src blob:; object-src 'none'; child-src 'none'`. CSP policies combine by
intersection, so ours meets the library's at `blob:` — exactly the line between
Readium's own injected scripts, which arrive as `<script src="blob:...">`
(`Injector.ts`), and the book's, which never do.

**Rejected: dropping `allow-scripts`.** Readium injects `css-selector-generator`
into every document (`epubInjectables.ts`), and that is what turns a browser
selection into a Locator — §2's write path, and the ground epic #827 stands on.

**Rejected: dropping `allow-same-origin`.** An opaque-origin frame cannot be
scripted by its parent at all, which is how the navigator drives it.

**Residual, accepted for now.** This is a mitigation, not a sandbox: the frame
is still same-origin, so anything that does get script running there has the
page. Scripted EPUB content does not work, which is the intended trade. The
architectural fix is a separate origin for publication resources; Readium's
blob-URL design makes that awkward and no ticket carries it.

**Residual closed at the source.** The part of that residual about *documents
loaded directly* rather than framed — a frame navigating itself, or any path
reaching a resource URL without the sanitising fetch — is handled by the server:
`GET /api/v1/readium/books/{book_id}/resources/{path}` answers with
`Content-Security-Policy: sandbox` on both 200 and 304, giving such a document
an opaque origin and no scripts whatever the frontend does. It costs the reader
nothing, because the navigator reads the response as *text* and frames a blob it
builds itself. `SecurityHeadersMiddleware` was changed in the same place to
leave a response's own policy alone rather than overwrite it.

## Amendment 3: how web reading becomes reading sessions

- **Date:** 2026-09-07
- **Resolves:** #742 (M2.3), the second of the two decisions left *Pending*
  above
- **Built by:** R4.4 (#830) and R4.7 (#833). None of it is on `main` yet; both
  tickets carry this amendment as the plan of record.

Reading progress is the `end_position` of the latest row in `reading_sessions`,
and the statistics page is `ReadingStatisticsCalculator` over every row of it.
Neither knows the web reader exists, so this amendment settles what the browser
has to write for those two to keep being right.

### The reader writes real reading sessions

**Web reading produces ordinary `reading_sessions` rows** — the same table, the
same columns, the same meaning — rather than a parallel notion of progress the
progress bar and the calculator would have to learn about. Nothing in `reading`
changes, and a session made in the browser shows up in the statistics, the
activity grid and the book-details view because it is not a special kind of
row.

A session is written by the position endpoint itself, on the request that
reports a position:

- **It starts on the first position write after the book is opened**, not on
  opening. The navigator announces where it is as soon as a frame loads, so
  "opened" is a moment the browser reports whether or not anybody reads
  anything. The frontend remembers the position the book opened at and writes
  only once it *changes*, so opening a book and closing it again records
  nothing.
- **It grows on every write after that.** `end_time` becomes the moment
  reported and `end_position` where the reader now is, while the xpoint range
  is extended to the furthest the session reached (`ReadingSession.extend_to`).
  A reader paging backwards moves `end_position` back with them; the range keeps
  its furthest extent, because a range that ran backwards would not be one.
- **It is kept alive while the reader is on one page.** Sitting still is not
  having stopped, so the reader re-sends its position every ten minutes while
  the tab is visible — a third of the idle window below — and an unchanged
  position is still a position arriving. A hidden tab sends nothing, which keeps
  a book left open overnight from recording a night's reading.
- **It ends by not being extended.** **Nothing has to run to close a web
  reading session.** Its `end_time` is already the last position it was told
  about, so a session that stops being extended is over the moment it stops.
- **A gap decides where one sitting is cut from the next.** A write arriving
  more than `WEB_READING_SESSION_IDLE_SECONDS` (default 30 minutes) after the
  open session's end starts a new session. Generous on purpose: over-counting is
  structurally impossible, so the timeout decides only *granularity*.
- **Leaving the book closes it explicitly.** The frontend's last write carries
  `closing`, which clears the pointer to the open session so the next sitting
  starts fresh however soon the reader comes back. Written with a `keepalive`
  fetch, the only kind of request a page may leave behind.

The session records `device_id = "crossbill-web-reader"`, a name three places
share (`domain/common/devices.py`, since §6 keeps `reading` from depending on
the web reader existing). It keeps browser reading distinguishable in the
sessions list, and its content hash from colliding with a KOReader session.

**A session's pages are Readium position numbers.** `start_page` / `end_page`
have never been a canonical pagination — a KOReader session carries *that
device's* page numbers, which depend on its screen and its font — so the honest
equivalent for a browser session is this API's position list, which the reader's
chrome counts "Page X of N" from. The number arrives as `locations.position`,
and a value outside Readium's 1-based list is treated as absent, not refused.
The range keeps the furthest the sitting reached, as the xpoint range does.

Leaving them null was not merely a blank line on a card: the activity grid
counts pages only when **every** session of a book has them
(`ActivityUnitRule.EVERY_SESSION_PAGED`), so one page-less web session silently
rewrote a KOReader-read book's whole year from pages into minutes.

**A jump back across the book is a new sitting.** Somebody who finishes a novel
and starts it again half an hour later would otherwise be one sitting reporting
three hundred pages with a progress bar on page one. So a backward jump of more
than **a quarter of the book** ends the sitting: a quarter is navigation, not a
sequence of page turns, and re-reading the previous chapter sits inside it.

### The new table is a bookmark, not a second source of truth

`web_reading_positions` (one row per reader and book) holds the Readium locator,
the xpointer it converted to, the resolved `Position`, when it was recorded, and
the id of the session still being extended. **It is not where "how far through
am I" is answered** — that stays the latest session's `end_position`. It holds
the two things a session cannot: the locator, so a browser can be put back
precisely where it was (*Amendment 4*), and the open-session pointer.

> **Amended by *Amendment 6*.** The row carries a `locator_source_hash` as well,
> so the browser's own stored locator can be told it is stale after an EPUB
> replace. See *Null is a real answer*.

### Endpoints, and where they live

`GET` and `PUT /api/v1/readium/books/{book_id}/reading-position`, under the
`readium` prefix rather than `/books/{id}/` as #742's body wrote it. The prefix
is now inherited rather than argued: #830 may keep it or move the routes out.

> **Amended by R1 and R4.4 (#830).** Both routes are **Bearer-only**, whatever
> prefix they keep: the publication cookie must not open a write, which is what
> makes it read-only by construction (*Amendment 1*). The departing write sets
> `Authorization` from `getAccessToken()` explicitly — a `keepalive` fetch can
> carry a header.

The `PUT` body is the locator as the navigator serializes it, plus `recorded_at`
and `closing`. An overtaken write is answered with what is stored rather than
refused: the debounced write and the one a closing tab sends race by design.

### A reading position usually has no quote at all

**Corrected 2026-09-07, from the maintainer's own reading.** The paragraph this
replaces assumed a reading position arrives with a text quote and a CSS
selector. It arrives with neither: `EpubNavigator` reports a page turn in a
reflowable book from its column snapper's `progress` event, and the Locator it
builds carries an `href`, a `position`, a `progression`, an empty `fragments`
array and no text whatever. Every real position write was therefore refused,
while every test passed, because the fixtures were shaped like a **selection**.

So the conversion synthesises a quote out of the document itself when the
Locator brought none, and hands it back through the same tested conversion the
quote path uses. `AnchorSource` records which of three it was: **`QUOTE`**, the
Locator's own text, what a selection produces; **`ELEMENT`**, the first run of
text in the element a `cssSelector` or fragment id names; **`PROGRESSION`**, the
text at that fraction of the resource — what a page turn produces, and therefore
the ordinary case rather than the exotic one.

### The confidence floor, one per kind of anchor

§5 requires callers to reject weak matches. The three anchors are not points on
one scale, so each is **capped** at what the Locator's own evidence was worth
and compared against its own floor, rather than all three against one:

| Anchor | Ceiling | Floor | Because |
| --- | --- | --- | --- |
| `QUOTE` | `BOTH_CONTEXTS` | `HIGHLIGHT_ONLY` | Graded on evidence the caller supplied — §5's case exactly |
| `ELEMENT` | `HIGHLIGHT_ONLY` | `HIGHLIGHT_ONLY` | Names one place, corroborated by nothing else |
| `PROGRESSION` | `FUZZY` | `FUZZY` | Approximate by construction, and accepted anyway |

`HIGHLIGHT_ONLY` for a quote refuses exactly the two grades that mean *we do not
know which place this is*: `FUZZY`, the quote not being in the book as written,
which is the shape a replaced edition takes, and `AMBIGUOUS`, the quote
occurring several times with neither context settling which. That is one grade
below what a *highlight* will demand (#831): a highlight in the wrong paragraph
is a lasting falsehood about what the reader marked, while a reading position
that is off costs a moment finding one's place.

**Accepting `PROGRESSION` is the load-bearing choice here**, and it is what the
live failure taught: a floor that refused an approximate anchor would refuse to
record reading at all, since almost every reading position *is* one. What still
refuses is the conversion failing outright — a Locator naming a resource the
book does not have — and a refusal is **422**, not 400: the request is well
formed and the caller could not have sent anything better.

Asking the frontend for a richer Locator was rejected: the snapper's `progress`
message has no text in it, and scraping the iframe's DOM on every page turn
makes the *client* do work the server already has the parsed book for.

### Concurrency, and the two clocks

Two tabs of the same book write independently. **The position is claimed first,
in one conditional upsert, and the session is written only by the request that
won the claim** — `INSERT … ON CONFLICT (user_id, book_id) DO UPDATE … WHERE
updated_at < :written_at`, with the open-session pointer attached under `WHERE
updated_at = :written_at` so only the latest writer may move it. (Residual: two
genuinely simultaneous *first* writes can each create a session between the two
statements, leaving one stray zero-second row.)

**`updated_at` is the server's clock**, and it decides *whether a write happens
at all*. Ordering on the reader's own clock reads well until a second device is
five minutes slow, at which point every write it will ever make is older than
what is stored and is refused for good — a permanent, silent failure to record
anything.

**`recorded_at` is the reader's clock**, and it decides *whether a write moves
the position*. Arrival cannot answer that: a tab idling on page 20 while another
reads on to page 100 sends its dying write **last**, carrying a page its reader
left an hour ago. So the upsert carries both conditions, and a write that does
not move the position still lands — it extends the sitting, and closes it if
that is what it came to say. This is also why a heartbeat carries the
observation's own moment rather than the moment it fires.

**Neither clock measures reading.** A session's start and end are the server's
clock alone, so no client can be credited with time it did not spend — a
stronger guarantee than any bound on what a client may claim.

### What a locator may claim, and what the book learns

Both numbers a locator carries are bounded at the schema, and again inside the
anchor port on its own account, since a port is reachable from more than one
caller. Both feed arithmetic. `locations.position` is an index the browser read
out of a position list *this API served it*, so its ceiling is
`MAX_PUBLICATION_POSITIONS`; an
unbounded one is a 500 or billions of pages credited. `locations.progression` is
multiplied by a resource's length and rounded, so `NaN` and `Infinity` — which
JSON has no literal for but Python's parser reads anyway — become 500s out of
`round()`; non-finite values are read as *no progression* rather than refused,
because a 422 body quoting `NaN` back cannot itself be serialised.

**The book's own `end_position` is backfilled on the way past.** Progress is a
fraction of it, and until now only the KOReader upload path ever measured a
book's length, so a book read only in the browser had no denominator.

### Not adopted

- **A background job to close idle sessions.** There is nothing to close; a
  sweeper would exist only to write an `end_time` that is already correct.
- **Ordering two writes by the reader's clock.** It trades a sub-second
  reordering for a device with a slow clock never recording anything again.
- **A `web_reading_progress` notion of its own**, read by the progress bar
  instead of sessions. A second answer to a question that already has one.
- **Writing a position on open.** It would start a session for opening a book,
  and — once a resume restores a stored position — write that position back.
- **Any change to the plugin surface.** No `koreader-plugin` minimum bump.

## Amendment 4: resuming from the latest position of any device

- **Date:** 2026-09-07
- **Resolves:** #743 (M2.4)
- **Built by:** R4.4 (#830), the read half, and R4.7 (#833), the reader

*Amendment 3* settled what the browser writes. This settles what it reads back,
a wider question than it looks: somebody who read three chapters on their
e-reader last night expects the book to open there, not where this browser was
last week.

### The later of two sightings wins

`GET /api/v1/readium/books/{id}/reading-position` answers **where the book
should open**, not what the browser last stored. Two candidates, weighed on
when the reader was at each:

1. **The stored web position**, at its `recorded_at`. It carries the locator
   verbatim.
2. **The end of the latest reading session another device wrote**, at its
   `end_time`.

Ties go to the stored web position, because it is the row the reader themselves
last moved.

> **Amended by *Amendment 6*.** Candidate 2's locator was derived from the
> session's xpointer on the way out. It is now a stored column (#839), read like
> candidate 1's; a session whose locator is null or stale is answered
> `unresolved` rather than re-derived. **This read runs no EPUB parse at all.**

### Sessions the web reader wrote are left out of (2), and that is the dedupe

A web write records a position and an ordinary `reading_sessions` row about the
same moment, so such a session never adds information — but it would frequently
*win*, because its `end_time` is the **server's** clock while the position's
`recorded_at` is the **reader's**. A reader whose clock runs a minute behind
would have their exact stored position thrown over for a session row about the
same page. Filtering on `device_id` is what stops it.

**The sync refuses that id** (422). A synced session wearing it would be taken
for the browser's and left out of the search for ever — a wrong answer rather
than a missing one. Crossbill minted the name for its own sessions, so refusing
it takes nothing from any client that exists and needs no plugin bump.

### A synced session must name an instant

The comparison above puts a device's clock against a browser's, so **session
moments must carry a UTC offset** and are normalised to UTC at the schema — a
rule `main` does not yet enforce (`reading_session_schemas.py:43-44` takes a
bare `datetime`), and R4.4 (#830) now carries it. The related rule — the sync
refusing `crossbill-web-reader` as a `device_id` — has no ticket yet; it touches
`/reading_sessions/sync`, so whoever adds it weighs a `koreader-plugin` minimum
bump. A naive value handed to a
`timestamptz` column is read in the connection's time zone, so the same request
denotes different instants on different deployments and would put a device in
Helsinki three hours into its own future.

This is deliberately **not** the rule the highlight path follows: KOReader's
annotations carry the device's own wall clock with no offset to parse. Sessions
are built from Unix epochs through `os.date("!%Y-%m-%dT%H:%M:%SZ")` and always
have been, so requiring here what the plugin has always sent breaks no released
version — again, no bump. `as_aware` stays what it was, a rule about **storage**
repairing the offset SQLite drops, sound only while no boundary lets a client's
naive timestamp reach a column.

### Verification, for this direction, is "it resolved"

§5 requires a derived anchor to be verified against the stored text. A *reading
position* has no stored text — unlike a highlight, that is the whole difference
between them — so there is nothing to compare a locator against. What the
response reports instead is `source` and `unresolved`: a position that cannot be
placed against the EPUB now held is the shape a replaced edition takes, and the
reader is told their place was lost rather than dropped at page one.

### Dwelling is reading; arriving is not

The browser opens the book *at* the restored place, through the navigator's
constructor, so there is no visible jump and no navigation to write down. The
position writer suppresses everything reported while the book is being built —
the place it opened at, the place the frame settled on once the columns were
laid out — because nobody has turned a page in a book not yet on screen.

The bracket is drawn around **time**, not around the restored locator: a hold
that asked "is this still the place we restored to" would swallow a reader
turning pages through a long chapter, since a position is a span of the resource
and not a rendered page. Once the book has arrived, every report is the
reader's.

The heartbeat is deliberately untouched, so a restore **alone** writes nothing
while a restore plus ten minutes of reading writes, because of the reading —
exactly as it does for somebody who opens a new book and reads its first page
for ten minutes. Closing the ten-minute granularity would mean writing on open,
which *Amendment 3* rejects, or a dwell threshold with no measurement behind
it.

## Amendment 5: the §4 measurement, and what it decided

- **Date:** 2026-09-08
- **Resolves:** the measurement §4 scheduled, made in #745 (M3.1)

> **Superseded by *Amendment 6* (2026-09-13).** Persistence was adopted, on
> grounds this measurement did not weigh — not on a second measurement, and not
> because the number moved. The numbers and the diagnosis below stand;
> `Crossbill-App/xpoint-cfi#3` is still worth fixing. Read Amendment 6 before
> acting on this section's decision.

§4 said derivation stays on demand unless conversion costs more than roughly
**200 ms per book**, in which case a follow-up persists anchors and this ADR
gets an amendment. The measurement was made against the development clone: 15
books carrying xpointed highlights, 356 highlights between them, EPUBs from 0.08
to 8.5 MB. It came out **over the line**, and this is the amendment — but not
the one §4 anticipated, because the number is not where it was expected.

### The numbers

| | worst | typical |
| --- | --- | --- |
| Parse (`EpubMap.from_bytes`) | **1.0 ms** | ~0.5 ms |
| Convert every highlight of the book | **561 ms** (54 highlights) | 1–40 ms |
| Whole book, cold cache | **531 ms** | |

Second worst: 154 ms for 20 highlights. Everything else finished inside 45 ms.

### Parsing is not the cost, and the per-book cache buys nothing here

Converting the worst book a second time against the **already parsed**
publication took 533 ms against 531 ms cold. Cold and warm are the same number,
which settles two things at once.

The first is that §4's per-book cache — the thing this ADR built to make a whole
book cost one parse — **does not help the books that are slow**. It was not
wrong to build: it keeps a book's list from re-parsing the file per highlight,
and the measurement above is only one parse deep *because* of it. But the cost
it amortises turns out to be ~1 ms, and the cost that hurts is per *highlight*
and amortises against nothing.

The second is that **caching a parsed publication more widely is not worth
building**, which answers the review suggestion (#734) that the manifest path's
reparse be cached alongside the anchor cache. That parse costs at most
**2.9 ms** across the same corpus. A cache for it would buy single-digit
milliseconds and add a second thing that must be evicted correctly — the failure
mode this ADR calls out as noisy. Not adopted, on the measurement. (Unmeasured,
and the one thing that could change this: the numbers price a parse of bytes
already in hand, not an S3 fetch of them. If the manifest is ever slow in
production, the fetch is what to measure.)

### Where the time actually goes

A profile of the worst book puts **2.1 of its 2.2 seconds** inside
`xpoint_cfi.css_selector.resolve_selector` → `_matches_compound` → `_nth_child`
→ `element_children`: generating a CSS selector for a highlight involves proving
the selector unique, which rescans sibling lists, once per candidate. Books
built as a few flat, enormous spine documents pay about **10 ms per highlight**;
well-structured books pay about **0.2 ms**. The 561 ms is therefore not "large
book" — the 8.5 MB book in the corpus converts 44 highlights in 13 ms — it is
*flat* book.

### Decision: fix the generator, do not persist anchors

**Persistence is not adopted.** It would be building a second copy of every
position — the thing §4 warns is a second source of truth that can silently
disagree — to work around a quadratic loop in a library we own, in a repository
we can change. Filed as **Crossbill-App/xpoint-cfi#3**: build the sibling index
once per parent rather than rescanning per call.

**Persistence remains the fallback, not a closed door.** If the library fix
under-delivers — if a real book still costs more than ~200 ms after it — the
case §4 makes reopens on the same terms, with a second measurement behind it.

### What this ticket did instead, and it is not a substitute

**None of it is on `main`.** M3.1 was a measurement with a spike behind it, and
the spike was never merged. What follows is the reasoning as it stood; it is
recorded because the measurement rests on it, not because the code exists.

The spike derived locators only for the highlights a view would actually render,
so a search showing three matches of a heavily annotated book converted three
rather than all of it. Worth having whatever the library did, but it did not
answer the question above: a reader **drawing every decoration in a book** asks
for the whole list by construction, and on a flat book with a couple of hundred
highlights that was seconds. R4.5 (#831) was where that number would have been
met in earnest — until *Amendment 6* took the conversion off the read path
altogether, which is what makes that draw one `SELECT` instead.

One thing the measurement settled on the spot: derivation belongs off the event
loop (`asyncio.to_thread`), the parse included. Half a second of lxml inline on
the loop is half a second of every other request in the process, which the
per-book cache had been quietly hiding. That holds for the ingest paths
*Amendment 6* moves the conversion onto, which is where it now has to be done.

## Amendment 6: locators are derived at ingest and stored

- **Date:** 2026-09-13
- **Resolves:** #828 (R4.1, part of epic #827)
- **Reverses:** §4

§4 said a locator is computed at request time and nothing is persisted. **It is
now computed when a position arrives, and written to a column.**

### §1 still holds, and that is why the reversal is small

The xpointer remains the canonical position for everything KOReader syncs. A
stored locator is a **derived column** beside it, carrying a
`locator_source_hash` naming the EPUB it came from. That gives it the standing
`highlights.position` and `reading_sessions.start_position` / `end_position`
already have. A derived column is not a second source of truth: where it
disagrees with the xpointer the xpointer is right, and the hash says so.

### What broke §4

**The repo already does exactly this, for a sibling value.** Positions are
resolved from the xpointer at ingest and rewritten when the file changes:

| Where | What it does |
| --- | --- |
| `highlight_upload_use_case.py:167-172`, `:213-215` | Builds a `PositionIndex` from the EPUB on the sync path, resolves each incoming highlight against it |
| `reading_session_upload_use_case.py:120-125`, `:250-261` | The same for a session's two endpoints |
| `ebook_upload_use_case.py:204-234` (`_backfill_positions`) | Rewrites every existing highlight and session of the book when an EPUB arrives |

§4 argued from first principles and did not look at the precedent in the tree.
Against it, a locator derived on the fly was the odd value out rather than the
safe one, and the machinery a stored one needs already exists.

**Files do not change in practice, and there is a marker when one does.** The
cost §4 was avoiding is a stored value silently disagreeing with the file it
describes. `book_publications.content_hash` (R1,
`infrastructure/web_reader/orm/book_publication_model.py`) already names the
digest of the EPUB a derived row came from, and `locator_source_hash` says the
same per row: disagreement is detectable, not silent.

**§1's premise stopped being true — in the reverse direction.** §4 rests on §1's
argument that the xpointer must stay canonical because KOReader is the only
client that *writes* a position, so converting at ingest would put a conversion
failure on the path where it loses data, while deriving on read only loses a
view. The browser is already a position writer in R4.4 (#830), and once it makes
highlights (M4, #749 — a later milestone, not this epic), a locator is the
*input* for those rows and the xpointer is the derived side. That is what makes
an ingest conversion unavoidable in the **reverse** direction. It does not by
itself decide the **forward** one, which is what §4 was about: the bridge is
only that deriving forward on read, beside a reverse path that converts at
ingest, is inconsistent. Consistency is the lightest of the three legs, and on
its own it would not have outweighed the cost §4 named — it is the precedent and
the hash that carry the reversal.

**Amendment 5's case is unchanged; what it could not see is the writer.** It
measured 561 ms for the worst book, found the cost inside a quadratic selector
generator (`Crossbill-App/xpoint-cfi#3`, still open) and declined to persist
anchors to work around a bug in a library we own. That reasoning stands and this
amendment does not overturn it: the library fix is still worth making, and
persistence is no substitute for it. What changed is not the number — it is that
the browser became a writer, so a converting write path has to exist whatever
the generator costs. Storing what that path produces is not free: R4.2 (#839) is
a migration, three ingest wirings and a `LOCATOR_BACKFILL` job batch. What it is
not is a *new* mechanism — it is the conversion that write path already runs,
written down.

### What does not change: the reverse conversion still needs the EPUB

`book_publications.publication` is manifest-level only — reading order, hrefs,
media types, table of contents, metadata, no DOM whatever
(`application/web_reader/publications.py`) — so nothing stored can answer "which
text node does this selector name" without the EPUB bytes and an lxml parse. A
locator the browser writes is still fetch, parse, convert, verify, store both
(#830).

Only the **read** paths lose the EPUB dependency, and they lose it completely: a
view renders a highlight from its stored locator, and drawing every decoration
in a book (#831) is one `SELECT` rather than a whole-book conversion. §4's
parsed-publication LRU, its content-hash key and its eviction go with them.

### The design that replaces the cache: a batch, not a cache

The anchor port takes **EPUB bytes and a mapping of xpointers**, and converts
the mapping against one parse. Every caller is an ingest loop over a book's rows
and already holds the bytes, so there is no cross-request cache, no eviction
rule, no content-hash cache key and no fan-out for an upload to remember.

Amendment 5's own numbers are why a batch is enough where a cache was not.
Parsing is ~1 ms, and the worst book converted in 533 ms warm against 531 ms
cold: what the cache amortised was the cheap half, and a batch amortises exactly
the same 1 ms across the same rows. The expensive half is per highlight,
amortises against nothing, and leaves the read path by being stored rather than
by being cached.

### Null is a real answer

A missing locator, or one whose `locator_source_hash` no longer matches the
book's EPUB, is answered as **unplaceable**. No read path falls back to deriving
one.

**That includes `web_reading_positions`.** *Amendment 3* specifies that table
without a source hash, and it needs one on the same terms as the columns #839
adds. Its locator is candidate 1 of *Amendment 4*'s resume answer and wins ties
against the session row that #839 *does* give a hash, so without one the
browser's own position would be the one locator in the system that cannot be
told it is stale — restored confidently into an EPUB it no longer describes,
which is the failure §5 exists to prevent. The table is new in #830, so this is
a line of its spec rather than a migration.

This is the load-bearing half of the reversal rather than a caveat on it. A
fallback would put the bytes, the parse, the port and the failure handling back
on every read path for the rare row — the whole of the complexity this amendment
removes, kept alive for the case that exercises it least and is hardest to test.
§5 already holds that the honest answer to "we cannot locate this" is to say so
per item; a stale locator is one more shape of that. Backfill is what keeps null
rare: R4.2 (#839) fills the columns wherever `position` is already filled, at
sync and for the whole book when an EPUB arrives.

### Open: a failed reverse conversion is still a rejected write

*Explicitly NOT adopted* holds that a browser selection whose derived xpointer
does not match the selected text is a failed write rather than a stored guess.
That rule was written when the only writer was a sync that could resend. With
the browser as a first-class writer it means **the reader loses a highlight they
just made**, on a page still showing the text they selected — a worse trade, and
one they cannot act on.

No R4 ticket writes a browser-made highlight — R4.5/R4.6 draw and jump to ones
ingest already placed — so the rule bites first in M4 (#749). The reverse
conversion R4.4 (#830) does ship is a *reading position*, where *Amendment 3*'s
`PROGRESSION` floor already accepts an approximate anchor.

The alternatives each carry a cost §1 was written to avoid: storing the locator
with a null xpointer defers the failure to whenever KOReader next reads the
book, and storing a low-confidence xpointer marked as such puts a guess in the
canonical column. **This amendment does not settle it.** The rejection stands
provisionally, #830 implements it and is asked to make it easy to find, and it
must be settled before M4 (#749) ships.

### Which tickets carry this

| Ticket | What it lands |
| --- | --- |
| #828 (R4.1) | The anchor port and its `xpoint-cfi` adapter, batch-shaped, storing nothing; this amendment |
| #839 (R4.2) | The locator columns, their `locator_source_hash`, and the backfill |
| #830 (R4.4) | The one route that still converts at write time |
