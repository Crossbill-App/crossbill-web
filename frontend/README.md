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
- Backend server running (for API client generation)

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
from the same app. It is also a requirement rather than a nicety: the reader
loads EPUB resources into iframes, and a cross-origin iframe cannot be scripted.

If your backend runs somewhere other than port 8000, change the proxy target in
`vite.config.ts` rather than pointing the frontend across origins.

### Building

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

`npm run preview` proxies `/api` the same way `npm run dev` does, so a built
bundle still needs the backend running to be worth looking at.

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

The project uses git hooks to automatically run linting and formatting before commits:

- **ESLint** - Checks and fixes code issues
- **Prettier** - Formats code and organizes imports

All code is automatically formatted and linted when you commit changes.

### Manual Quality Checks

Before committing, you can run:

```bash
npm run lint:fix && npm run format && npm run type-check
```

## Project Structure

```
frontend/
├── public/              # Static assets
├── src/
│   ├── api/
│   │   ├── generated/   # Auto-generated API client (gitignored)
│   │   ├── axios-instance.ts
│   │   └── base-url.ts  # Where the API's origin is decided
│   ├── components/
│   │   ├── common/      # Reusable UI components
│   │   ├── layout/      # Layout components (AppBar, etc.)
│   │   └── features/    # Feature-specific components
│   ├── hooks/           # Custom React hooks
│   ├── lib/
│   │   └── queryClient.ts
│   ├── routes/          # Tanstack Router file-based routes
│   │   ├── __root.tsx
│   │   └── index.tsx
│   ├── theme/
│   │   └── theme.ts
│   ├── types/           # TypeScript type definitions
│   ├── utils/
│   │   ├── date.ts      # Luxon date utilities
│   │   └── helpers.ts   # Lodash utility wrappers
│   ├── App.tsx
│   ├── main.tsx
│   └── routeTree.gen.ts # Auto-generated (gitignored)
├── .env                 # Environment variables (gitignored)
├── .env.example         # Environment template
├── eslint.config.js     # ESLint configuration
├── .prettierrc          # Prettier configuration
├── orval.config.ts      # API generation configuration
├── tsr.config.json      # Router configuration
├── tsconfig.json        # TypeScript configuration
├── vite.config.ts       # Vite configuration
└── package.json
```

## Path Aliases

The project uses TypeScript path aliases for cleaner imports:

```typescript
import { Button } from '@/components/common/Button';
import { useAuth } from '@/hooks/useAuth';
import { formatDate } from '@/utils/date';
import { api } from '@/api/generated';
```

## API Integration

The frontend uses **Orval** to automatically generate a type-safe API client from the backend's OpenAPI specification.

### Generating API Client

```bash
# Make sure backend is running at http://localhost:8000
npm run api:generate
```

This will:

1. Fetch the OpenAPI spec from `http://localhost:8000/api/v1/openapi.json`
2. Generate TypeScript types and React Query hooks
3. Place generated files in `src/api/generated/`

### Using Generated API

```typescript
import { useGetBooks } from '@/api/generated/books';

function BooksList() {
  const { data: books, isLoading } = useGetBooks();

  if (isLoading) return <div>Loading...</div>;

  return <div>{books?.map(book => book.title)}</div>;
}
```

## Development Guidelines

See [claude.md](./claude.md) for detailed development guidelines, including:

- Functional programming patterns
- Lodash usage examples
- Code quality requirements
- TypeScript best practices
- Component patterns

### Key Principles

1. **Always run linter and formatter before commits** (automated via pre-commit hooks)
2. **Prefer functional programming** - Use pure functions, avoid mutations
3. **Use Lodash** for functional utilities (map, filter, groupBy, etc.)
4. **Type everything** - Leverage TypeScript's type system
5. **Keep components small** - Single responsibility principle

## Environment Variables

The app reads one variable, and works without it.

| Variable       | Default            | Effect                                                                                 |
| -------------- | ------------------ | -------------------------------------------------------------------------------------- |
| `VITE_API_URL` | _empty_ (relative) | Absolute origin to send API requests to, e.g. a deployed backend. Overrides the proxy. |

Setting it is an escape hatch, not the normal path. Both dev (via the `/api`
proxy) and production (FastAPI serving the frontend) already put the API on the
app's own origin, and `VITE_API_URL` takes it back off that origin — which
breaks the reader's iframes and makes cookie-based token refresh depend on the
backend's CORS list. Use it only to point a local frontend at a backend
elsewhere.

To set it, copy the template and uncomment the line:

```bash
cp .env.example .env
```

Precedence is simply: `VITE_API_URL` if it is set, otherwise the empty
relative base. The single place that decides is `src/api/base-url.ts`, which
both the axios instance and the cover-image URLs read.

The test build sees no environment variables at all: `envPrefix: []` in
`vitest.config.ts` matches no name, so neither a local `.env` nor a variable
exported in your shell or set by CI can reach `import.meta.env`. `VITE_API_URL`
therefore cannot change what the MSW handlers have to match. `tests/setup.ts`
asserts `API_BASE_URL` is empty before the suite runs, so if that guard ever
comes off you get a sentence saying so rather than a puzzling
unmocked-request failure.

## Troubleshooting

### API Generation Fails

**Issue:** `npm run api:generate` fails

**Solutions:**

1. Ensure backend is running: `make dev-app` (from repo root)
2. Check backend URL in `orval.config.ts` matches your backend
3. Verify OpenAPI endpoint: `http://localhost:8000/api/v1/openapi.json`

### Import Path Aliases Not Working

**Issue:** TypeScript can't resolve `@/` imports

**Solutions:**

1. Verify `tsconfig.json` has paths configured
2. Verify `vite.config.ts` has aliases configured
3. Restart TypeScript server in your editor

### Pre-commit Hook Not Running

**Issue:** Pre-commit hook doesn't run

**Solution:**
The git hook is installed at the repository root (`.git/hooks/pre-commit`). It automatically runs when frontend files are changed.

## Contributing

1. Create a feature branch
2. Make your changes
3. Run quality checks: `npm run lint:fix && npm run format && npm run type-check`
4. Commit (pre-commit hooks will run automatically)
5. Push and create a pull request

## License

See repository root for license information.
