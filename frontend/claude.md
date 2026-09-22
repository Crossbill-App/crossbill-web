# Frontend Development Guidelines

## Quality gates

`npm run lint:fix`, `npm run format`, `npm run type-check`, `npm run knip`, and
`npm run duplication-check` must all pass before work is done — Husky runs
lint/format on staged files, CI runs everything.

### Dead code (knip)

`npm run knip` reports files, exports and dependencies nothing references. CI
fails on any finding, and a Stop hook runs it when frontend files are dirty.
Three ways a finding is legitimately resolved, in order of preference:

1. **Delete it** — the usual answer.
2. **Un-export it** — if the symbol is used inside its own file, drop the
   `export` rather than the code.
3. **Ignore it** — only for things knip cannot see (assets loaded by a runner,
   generated output). Add it to `frontend/knip.config.ts` with a comment saying
   why.

Never silence a finding by adding a fake import or re-export.

### Duplication (jscpd)

`npm run duplication-check` — same ratchet rules as `CLAUDE.md > Duplication`
at the repo root. The generated API client and route tree are excluded: Orval
and TanStack Router emit repetitive code that is not ours to refactor.

## API client (Orval)

The client is generated from the committed `backend/openapi.json` (no running
backend needed). After changing backend endpoints, run `make api-client` from
the repo root and commit the schema + regenerated client — CI fails if either
is stale. Never hand-edit files under `src/api/generated`.

## Conventions

- Functional style: pure functions, immutable data, functional components with
  hooks; lodash for functional utilities (`groupBy`, `debounce`, `memoize`, …).
- Prefer interfaces over types for object shapes.
- Server state via TanStack Query; invalidate queries after mutations.
- Styling: MUI components, the `sx` prop, and theme tokens — conventions and
  the theme source of truth are in the `frontend-design` skill.
- Never native `alert()`/`confirm()`: use `useSnackbar` from
  `@/context/SnackbarContext.tsx` for transient feedback and
  `ConfirmationDialog` from `@/components/common/ConfirmationDialog.tsx` for
  destructive actions.
- User-facing copy uses three periods for an ellipsis (`Saving...`,
  `Search highlights...`), never the `…` character. Prose in comments and docs
  may use either.
- User-facing copy is sentence case — dialog titles, tooltips, buttons, form
  labels, section headings, tab labels. `Delete highlight`, not
  `Delete Highlight`; `Confirm new password`, not `Confirm New Password`. Only
  proper nouns keep their capitals (Crossbill, KOReader, and whatever the
  reader's own books and chapters are called). There is no lint rule for this:
  a checker cannot tell a proper noun from Title Case, so it is on review.
- One label for committing a form: **Save** for editing something that already
  exists, and a named create (**Add flashcard**, **Add group**) only where the
  form is one of several controls on screen. Pending states are the verb in
  sentence case plus an ellipsis — `Saving...`, never `Updating...`.

## Testing

Three tiers. Which one a test belongs to is a decision about the code under it,
not a matter of taste.

**Pure logic** — `.test.ts`, in node. Parsers, arithmetic, normalisation:
genuinely tricky pure functions, where a page-level test could not pin down the
edge cases.

**Route tier** — `.test.tsx` through `renderApp`. Everything user-facing, and
the default for a new page or flow. A test renders a real route through the
real router, the real auth gate and the real providers, mocks the network with
MSW, and drives the page the way a user would.

**Component tier** — `.test.tsx` rendering a component directly. For components
with substantial behaviour of their own and a real engine or DOM contract to
hold to. A dialog with two arrow buttons is not one of these: it is proven by
the page that uses it. The allowlist, and what earns each entry:

- `src/components/reader/**` — the reader engine. It has grown enough behaviour
  of its own that driving it only through `/reader` would be slower and less
  precise, not better.
- `src/components/carousel/**` — paging arithmetic measured against a host of a
  width the test sets. At route level the host is the viewport, so the item
  pitch and the bleed margins cannot be pinned.
- `src/hooks/**` — a hook with no component of its own gets a small `Probe`
  component that uses it. `screen.rerender` stages the races these hooks exist
  for — a refetch landing mid-keystroke (#259) — which a route cannot
  reproduce.

The boundary is a lint rule, not a convention: importing `render` from
`vitest-browser-react` is an error in `src/**/*.test.tsx` outside that
allowlist, which lives in `eslint.config.js`. Widening it means adding the
directory there and a line here saying what earned it. `cleanup` is not
restricted — a route test that renders twice still needs it.

Run them with `npm run test` (headless Chromium via Vitest browser mode) or
`npm run test:watch`. `npx playwright install chromium` once, first time.

Vitest runs two projects, and the file extension picks the project:

- `unit` — `*.test.ts`, in node, with no setup file and no MSW. Pure logic
  only. `npm run test:unit` runs just these, in about a second.
- `browser` — `*.test.tsx`, in Chromium, with `tests/setup.ts`. Anything that
  renders, or that needs the real DOM (`DOMParser`, `Range`, layout).

`npm run test` runs both, and so does CI.

### What belongs in a test

- User-visible flows: open a dialog, edit, save, and assert the **list or page**
  reflects the change — not merely that the dialog closed.
- Error paths: make the endpoint fail and assert the snackbar reports it and the
  original data is still on screen.
- Queries by accessible role and name (`getByRole('button', { name: 'Save' })`).
  Scope to a container when a name is ambiguous, e.g.
  `screen.getByRole('dialog').getByRole('button', { name: 'Close', exact: true })`.
  Reach for `data-testid` only when nothing else works; giving the element a
  proper `aria-label` in `src/` is usually the better fix.

### What does not

- Shallow renders, snapshots, coverage targets.
- Rendering a component on its own outside the component tier above. Fold the
  behaviour into the route test that already exercises the component, or leave
  it to the route test that proves it by using it at all.
- Mocking hooks, contexts or modules. Mock **the network**, never the app.
  If a test needs a context stubbed, the test is at the wrong level.

### How it is wired

- `tests/harness/renderApp.tsx` — `renderApp({ path })` mounts the whole app at
  a path with a fresh QueryClient. Real browser history, because dialogs close
  themselves via `window.history.back()`.
- `tests/msw/` — request handlers. `auth.ts` holds the bootstrap defaults every
  test gets; `bookApi.ts` is the pattern for a stateful module: a factory
  returning `{ handlers, state }` whose PUT updates the record the next GET
  serves, so a mutation genuinely round-trips.
- `tests/fixtures/` — builders returning generated model types, so an API schema
  change breaks the fixture at compile time.
- `tests/setup.ts` — starts the worker and fails any test that hits an `/api/`
  endpoint nobody mocked. Unhandled requests are errors by design: a test must
  never pass while silently talking to an unmocked endpoint.

Copy `src/pages/BookPage/BookPage.test.tsx` (render) and
`src/pages/BookPage/Notes/NotesPage.test.tsx` (mutation flow + error path) when
adding tests for a new page. Tests live next to the page they cover.
