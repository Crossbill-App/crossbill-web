# Frontend Development Guidelines for Claude Code

## Code Quality Requirements

### Working style

- Always make logically separated commits when working on big changes

### Pre-Commit Checklist

- **ALWAYS** run linter before making commits: `npm run lint:fix`
- **ALWAYS** run formatter before making commits: `npm run format`
- Verify no TypeScript errors: `npm run type-check`
- Check for unused files, exports and dependencies: `npm run knip`
- Check for copy-paste duplication: `npm run duplication-check`
- Ensure all staged files pass quality checks

> Note: Husky pre-commit hooks will automatically run linter and formatter on staged files, but you should still manually verify before committing.

### Dead code (knip)

`npm run knip` reports files, exports and dependencies nothing references. CI
fails on any finding, and a `Stop` hook (`.claude/hooks/check-knip.sh`) runs it
when frontend files are dirty, so a turn that leaves dead code behind gets sent
back.

Three ways a finding is legitimately resolved, in order of preference:

1. **Delete it** — the usual answer.
2. **Un-export it** — if the symbol is used inside its own file, drop the
   `export` rather than the code.
3. **Ignore it** — only for things knip cannot see (assets loaded by a runner,
   generated output). Add it to `frontend/knip.config.ts` with a comment saying
   why.

Never silence a finding by adding a fake import or re-export.

### Duplication (jscpd)

`npm run duplication-check` runs jscpd (v5, the Rust engine) over `src` and
`tests` and reports every copy-pasted block of 5+ lines / 50+ tokens. It exits 1
once duplicated lines pass the `threshold` in `frontend/.jscpd.json`.

The generated API client and the generated route tree are excluded: Orval and
TanStack Router emit repetitive code that is not ours to refactor.

Output is the compact `ai` reporter, one line per clone; add `--reporters
console` for columns and token counts.

The threshold is a **ratchet** — it may fall, never rise. When a refactor drops
the percentage, lower the threshold to the new number in the same commit. Never
raise it to make the check pass; extract the shared code instead.

A `Stop` hook (`.claude/hooks/check-duplication.sh`) runs jscpd when frontend
sources are dirty and sends the turn back if the threshold is passed, or if a
clone overlaps lines the turn changed. Pre-existing clones in files you touched
stay quiet, so a finding is about code this turn wrote — extract it. See
`CLAUDE.md > Duplication` at the repo root.

## Programming Style

### Functional Programming Principles

- **PREFER** functional programming style over imperative
- Use pure functions whenever possible (no side effects)
- Avoid mutations - prefer immutable data structures
- Use functional composition for complex logic

### Component Patterns

- **PREFER** functional components over class components
- Use hooks for state management and side effects
- Keep components small and focused (single responsibility)
- Extract reusable logic into custom hooks

### Lodash Usage

- **USE** lodash for functional utilities when necessary:
  - `map`, `filter`, `reduce` for array transformations
  - `groupBy`, `sortBy`, `uniqBy` for data manipulation
  - `debounce`, `throttle` for performance optimization
  - `memoize` for expensive computations
  - `isEmpty`, `isNil`, `has` for safe checks

### Examples

#### Good - Functional Style with Lodash

```typescript
import { map, filter, sortBy } from 'lodash';

// Pure function
const getActiveHighlights = (highlights: Highlight[]) => {
  return sortBy(
    filter(highlights, (h) => !h.archived),
    'created_at'
  );
};

// Functional component
const HighlightsList = ({ bookId }: Props) => {
  const { data: highlights } = useHighlights(bookId);

  const activeHighlights = useMemo(
    () => getActiveHighlights(highlights ?? []),
    [highlights]
  );

  return map(activeHighlights, (highlight) => (
    <HighlightCard key={highlight.id} highlight={highlight} />
  ));
};
```

#### Bad - Imperative Style

```typescript
// Avoid mutations and imperative loops
const HighlightsList = ({ bookId }: Props) => {
  const { data: highlights } = useHighlights(bookId);
  const [activeHighlights, setActiveHighlights] = useState([]);

  useEffect(() => {
    const active = [];
    for (let i = 0; i < highlights.length; i++) {
      if (!highlights[i].archived) {
        active.push(highlights[i]);
      }
    }
    active.sort((a, b) => a.created_at - b.created_at);
    setActiveHighlights(active);
  }, [highlights]);

  return activeHighlights.map(/* ... */);
};
```

## TypeScript Best Practices

- **ALWAYS** define explicit types for component props
- **PREFER** interfaces over types for object shapes
- **USE** type inference when obvious
- **AVOID** `any` - use `unknown` if type is truly unknown
- **USE** strict null checks - handle `undefined` and `null` explicitly

## State Management

- **USE** Tanstack Query for server state
- **USE** React hooks (useState, useReducer) for local component state
- **CONSIDER** Context API for shared UI state
- **AVOID** prop drilling - use composition or context

## API Integration

- **USE** generated API client from Orval
- The client is generated from the committed `backend/openapi.json` (no running
  backend needed). After changing backend endpoints, run `make api-client` from
  the repo root and commit the schema + regenerated client — CI fails if either
  is stale
- **NEVER** hand-edit files under `src/api/generated`
- **ALWAYS** handle loading and error states
- **USE** optimistic updates for better UX
- **INVALIDATE** queries after mutations

## Styling

- **USE** Material UI components when available
- **USE** MUI's `sx` prop for component-specific styles
- **USE** theme tokens for consistent spacing/colors
- **AVOID** inline styles except for dynamic values

### Component Usage

- **ALWAYS** use semantic MUI components (`Button`, `IconButton`, etc.) instead of `Box` with `component="button"`
- **NEVER** use `<Box component="button">` - use `<Button>` instead for proper accessibility, keyboard navigation, and built-in interactions
- Proper MUI components provide better accessibility (focus management, ARIA attributes) and user experience (ripple effects, disabled states)

## File Organization

- **GROUP** related components in feature folders
- **EXTRACT** reusable components to `components/common`
- **KEEP** route components in `routes/` folder
- **PLACE** business logic in separate utility files

## Performance

- **USE** `useMemo` for expensive computations
- **USE** `useCallback` for function props
- **USE** lodash `debounce` for search inputs
- **USE** `React.lazy` for code splitting
- **MEASURE** before optimizing

## Error Handling

- **ALWAYS** handle API errors gracefully
- **PROVIDE** user-friendly error messages
- **LOG** errors to console for debugging
- **USE** error boundaries for component failures

## User Feedback & Confirmations

### Notifications (Snackbar)

- **NEVER** use native `alert()` - use `useSnackbar` from `@/context/SnackbarContext.tsx`
- **USE** for error notifications, success messages, and transient feedback
- Snackbar auto-dismisses after 6 seconds

```typescript
import { useSnackbar } from '@/context/SnackbarContext.tsx';

const MyComponent = () => {
  const { showSnackbar } = useSnackbar();

  const handleError = () => {
    showSnackbar('Failed to save. Please try again.', 'error');
  };

  const handleSuccess = () => {
    showSnackbar('Saved successfully!', 'success');
  };
};
```

### Confirmation Dialogs

- **NEVER** use native `confirm()` - use `ConfirmationDialog` from `@/components/common/ConfirmationDialog.tsx`
- **USE** for destructive actions (delete, discard changes, etc.)

```typescript
import { ConfirmationDialog } from '@/components/common/ConfirmationDialog.tsx';

const MyComponent = () => {
  const [confirmOpen, setConfirmOpen] = useState(false);

  return (
    <>
      <Button onClick={() => setConfirmOpen(true)}>Delete</Button>
      <ConfirmationDialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={handleDelete}
        title="Delete Item"
        message="Are you sure you want to delete this item?"
        confirmText="Delete"
        confirmColor="error"
      />
    </>
  );
};
```

## Accessibility

- **USE** semantic HTML elements
- **PROVIDE** alt text for images
- **ENSURE** keyboard navigation works
- **USE** ARIA labels when necessary

## Code Comments

- **WRITE** comments for complex business logic
- **DOCUMENT** utility functions with JSDoc
- **EXPLAIN** non-obvious workarounds
- **AVOID** obvious comments

## Git Workflow

- **COMMIT** frequently with descriptive messages
- **RUN** `npm run lint:fix && npm run format` before committing
- **VERIFY** no console errors before pushing
- **KEEP** commits focused on single changes

## Testing

Behavior tests over whole routes are the only tier. A test renders a real route
through the real router, the real auth gate and the real providers, mocks the
network with MSW, and drives the page the way a user would.

Run them with `npm run test` (headless Chromium via Vitest browser mode) or
`npm run test:watch`. `npx playwright install chromium` once, first time.

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

- Component-internal tests, shallow renders, snapshots, coverage targets.
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

Plain node-environment unit tests are reserved for genuinely tricky pure logic
in `src/utils` — parsing, normalisation, arithmetic — where a page-level test
could not pin down the edge cases.
