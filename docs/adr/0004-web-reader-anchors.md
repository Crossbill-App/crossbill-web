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

Two decisions belong in this ADR and are not yet made. **Both will be appended
here as amendments once settled** — they are not separate ADRs, because both are
about how a web reading position gets in and out of the system.

- **Auth for iframe resource loads — M1.4 (#737).** The navigator loads each
  resource URL straight into an iframe, and the API's Bearer token is held in
  memory where an iframe load cannot send it. The candidate is a short-lived,
  httpOnly publication access cookie scoped to one book's resource path,
  mirroring the refresh cookie in `identity/routers/auth.py`; the rejected
  alternative to record is signed URLs, which are stateless but put the token in
  logs and in the manifest.
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
- **#737, #742** — see *Pending*.
