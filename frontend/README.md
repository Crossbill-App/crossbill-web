# Crossbill Frontend

Modern React application for managing and viewing book highlights from KOReader.

## Tech Stack

- **React 19+** - UI library
- **TypeScript 5+** - Type safety
- **Vite** - Fast build tool and dev server
- **Material UI** - Component library
- **Tanstack Router** - File-based routing
- **Tanstack Query** - Server state management
- **Orval** - API client generation
- **Luxon** - Date/time handling
- **Lodash** - Utility functions
- **ESLint + Prettier** - Code quality

## Getting Started

### Prerequisites

- Node.js 18+ and npm

### Installation

```bash
# Install dependencies
npm install
```

No `.env` is needed for the standard setup — see
[Environment Variables](#environment-variables) if you want one.

### Development

```bash
# Start the backend first (from the repo root)
make dev-app

# Start development server
npm run dev

# The app will be available at http://localhost:5173
```

The dev server proxies `/api` to the backend on `http://localhost:8000`, so the
app and the API share one origin — `http://localhost:5173`. Nothing in the
frontend names the backend's host: the API client's base URL is empty and every
request is relative to the page.

That mirrors production, where FastAPI serves the built frontend and the API
from the same app. It is a requirement rather than a nicety: the reader loads
EPUB resources into iframes and scripts them from the parent, which a
cross-origin document forbids.

If your backend runs somewhere other than port 8000, change the proxy target in
`vite.config.ts` rather than pointing the frontend across origins.

### Building

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

## Available Scripts

- `npm run dev` - Start development server (generates routes automatically)
- `npm run build` - Build for production (generates routes and API client)
- `npm run preview` - Preview production build
- `npm run routes:generate` - Generate Tanstack Router routes
- `npm run routes:watch` - Watch and regenerate routes on changes
- `npm run api:generate` - Generate API client from backend OpenAPI spec
- `npm run lint` - Run ESLint
- `npm run lint:fix` - Run ESLint and auto-fix issues
- `npm run format` - Format code with Prettier
- `npm run format:check` - Check code formatting
- `npm run type-check` - Run TypeScript type checking

## Code Quality

### Pre-commit Hooks

Husky (installed by `npm install` at the repo root) runs lint-staged before
each commit, which lints and formats the staged files with ESLint and Prettier.

### Manual Quality Checks

Before committing, you can run:

```bash
npm run lint:fix && npm run format && npm run type-check
```

## Path Aliases

`@/` resolves to `src/` (configured in both `tsconfig.json` and
`vite.config.ts`):

```typescript
import { formatDate } from '@/utils/date';
import { useGetBooks } from '@/api/generated/books/books';
```

## API Integration

The frontend uses **Orval** to automatically generate a type-safe API client from the backend's OpenAPI specification.

### Generating API Client

```bash
# From the repo root; no running backend needed
make api-client
```

This exports the backend's OpenAPI schema to `backend/openapi.json`, then has
Orval generate TypeScript types and React Query hooks from it into
`src/api/generated/`. Commit both; CI fails if either is stale.

### Using Generated API

```typescript
import { useGetBooks } from '@/api/generated/books/books';

function BooksList() {
  const { data: books, isLoading } = useGetBooks();

  if (isLoading) return <div>Loading...</div>;

  return <div>{books?.map(book => book.title)}</div>;
}
```

## Development Guidelines

See [CLAUDE.md](./CLAUDE.md) for the conventions (dead code, generated code, UI copy and i18n),
and [the frontend testing skill](../.claude/skills/writing-frontend-tests/SKILL.md) for the test policy.

## Environment Variables

The app reads one variable, and works without it.

| Variable       | Default            | Effect                                                                                 |
| -------------- | ------------------ | -------------------------------------------------------------------------------------- |
| `VITE_API_URL` | _empty_ (relative) | Absolute origin to send API requests to, e.g. a deployed backend. Overrides the proxy. |

Setting it is an escape hatch, not the normal path. Both development (via the
`/api` proxy) and production (FastAPI serving the frontend) already put the API
on the app's own origin, and `VITE_API_URL` takes it back off that origin —
which breaks the reader's iframes and makes cookie-based token refresh depend on
the backend's CORS list. Use it only to point a local frontend at a backend
elsewhere.

To set it, copy the template and uncomment the line:

```bash
cp .env.example .env
```

The single place that decides is `src/api/base-url.ts`, which both the axios
instance and the cover-image URLs read. The value is compiled into the bundle at
**build** time: for `npm run dev` that is the moment the server starts, but for
`npm run preview` the variable must be set when `npm run build` runs.

Tests never see it. `vitest.config.ts` sets `envPrefix: []`, so no environment
variable reaches `import.meta.env` during a test run, and `tests/setup.ts`
throws if one does.

## Troubleshooting

### Import Path Aliases Not Working

**Issue:** TypeScript can't resolve `@/` imports

**Solutions:**

1. Verify `tsconfig.json` has paths configured
2. Verify `vite.config.ts` has aliases configured
3. Restart TypeScript server in your editor

## License

See repository root for license information.
