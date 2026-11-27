---
name: writing-frontend-tests
description: Frontend testing policy — which tier a test belongs to, what to assert, how to wait without timers, and how the MSW harness is wired. Use when writing, changing or reviewing a frontend test (`*.test.ts`, `*.test.tsx`).
---

# Frontend testing policy

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

## What belongs in a test

- User-visible flows: open a dialog, edit, save, and assert the **list or page**
  reflects the change — not merely that the dialog closed.
- Error paths: make the endpoint fail and assert the snackbar reports it and the
  original data is still on screen.
- Queries by accessible role and name (`getByRole('button', { name: 'Save' })`).
  Scope to a container when a name is ambiguous, e.g.
  `screen.getByRole('dialog').getByRole('button', { name: 'Close', exact: true })`.
  Reach for `data-testid` only when nothing else works; giving the element a
  proper `aria-label` in `src/` is usually the better fix.
- `getByText` for formatted **values** — `Duration 1h 11m`, `Pages 102 – 115`,
  `63%` — where the format is the behaviour. Never for a sentence of copy: a
  test that quotes the app's wording back at it breaks on every rewrite, and
  the sentence-case and ellipsis conventions in `frontend/CLAUDE.md` mean rewrites keep coming.
  Ask for the state instead: `getByRole('status')` for an empty state,
  `getByRole('alert')` for a failure, `getByRole('alertdialog', { name:
/delete/i })` for a confirmation, or the affordance the state puts on screen
  — the bookmark rail is proven empty by its list being gone. Add the role or
  the label in `src/` if the state has none.

  A `no-restricted-syntax` rule in `eslint.config.js` rejects a `getByText`
  literal ending in `.`, `?` or `!`. Two things legitimately still hold a
  sentence, and both pass the rule by being named: prose the test wrote into
  its own fixture, and a message that is itself the behaviour under test —
  asserted from a constant, once, in the one test that is about it.

## What does not

- Shallow renders, snapshots, coverage targets.
- Rendering a component on its own outside the component tier above. Fold the
  behaviour into the route test that already exercises the component, or leave
  it to the route test that proves it by using it at all.
- Mocking hooks, contexts or modules. Mock **the network**, never the app.
  If a test needs a context stubbed, the test is at the wrong level.

## Waiting

A test never waits on the clock. `setTimeout`, `setInterval` and
`timers/promises` are lint errors in `src/**/*.test.*`, and so is a `timeout`
above 10 s: `testTimeout` in `vitest.config.ts` is the whole budget. Wait on
what the test is waiting for instead:

- a state: `expect.poll` or `expect.element`;
- a timer or a debounce: `fakeTheClock()` from `tests/harness/fakeClock.ts`,
  then `vi.advanceTimersByTimeAsync`;
- a slow answer: a handler held on `aHold()` and released by the test;
- an absence, which needs something to have had its chance:
  `tests/harness/settle.ts` — `afterTheAnswersRender(queryClient)` once every
  request is answered and rendered, `unmountAndAwaitItsWrites()` for the
  `keepalive` write a reader sends on its way out, `afterFrames(n)` for a
  scroll or a render that lands a frame late.

The Vitest plugin's rules are on too: every test asserts (a helper named
`expect…` or `assert…` counts), and nothing is skipped or focused.

## How it is wired

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
