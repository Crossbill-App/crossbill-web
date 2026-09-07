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

One decision belongs in this ADR and is not yet made. **It will be appended here
as an amendment once settled** — it is not a separate ADR, because it is about
how a web reading position gets in and out of the system. (The other, auth for
iframe resource loads, is settled below in *Amendment 1*.)

- **How web reading maps onto reading sessions — M2.3 (#742).** Reading
  progress is derived from the latest reading session's `end_position`, so the
  browser has to produce sessions or produce something the progress bar and
  `ReadingStatisticsCalculator` understand. The candidate is to create real
  sessions from the reader (start on open, end on close or idle, start/end
  xpoints converted from locators) so both keep working unchanged.

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
- **#742** — see *Pending*.

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
- **Scope** is the cookie's `path`, `/api/v1/readium/books/{book_id}/`. A
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
  minutes by default), and the cookie's `Max-Age` matches, so a dead credential
  is dropped rather than sent. The reader re-posts on the schedule it already
  refreshes its access token on. Longer would mean a session that has ended — a
  password changed, a refresh family revoked — could keep reading a book for
  longer than it could keep calling the API; shorter buys nothing, since
  everything this cookie opens is already open to the token that minted it.
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
