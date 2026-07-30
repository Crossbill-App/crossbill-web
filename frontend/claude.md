# Frontend Development Guidelines for Claude Code

## Code Quality Requirements

### Working style

- Always make logically separated commits when working on big changes

### Pre-Commit Checklist

- **ALWAYS** run linter before making commits: `npm run lint:fix`
- **ALWAYS** run formatter before making commits: `npm run format`
- Verify no TypeScript errors: `npm run type-check`
- Ensure all staged files pass quality checks

> Note: Husky pre-commit hooks will automatically run linter and formatter on staged files, but you should still manually verify before committing.

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

## Testing (Future)

- Write unit tests for utilities
- Write integration tests for user flows
- Aim for high coverage of business logic
- Test error states and edge cases
