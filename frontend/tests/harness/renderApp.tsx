import { SnackbarProvider } from '@/context/SnackbarContext';
import { routerOptions } from '@/router';
import { theme } from '@/theme/theme';
import CssBaseline from '@mui/material/CssBaseline';
import { ThemeProvider } from '@mui/material/styles';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider, createBrowserHistory, createRouter } from '@tanstack/react-router';
import { render } from 'vitest-browser-react';

interface RenderAppOptions {
  path: string;
}

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 1000 * 60 * 5,
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

/**
 * Every `QueryClient` a test has created since the last drain.
 *
 * A component can still have a request in flight for a moment after the test
 * that triggered it has moved on — opening a dialog fires a fetch nothing in
 * the test awaits, for instance. `tests/setup.ts`'s `afterEach` drains this
 * list and gives each client a bounded chance to go idle before resetting MSW
 * handlers, so that request lands on the handlers that were active when it
 * was made rather than being orphaned onto whichever later test's `afterEach`
 * happens to run when it finally resolves.
 */
export const pendingQueryClients: QueryClient[] = [];

/**
 * Renders the whole app at `path`: the real route tree, the real auth gate and
 * the same providers `src/main.tsx` mounts, over a fresh QueryClient.
 *
 * Real browser history rather than a memory history, because dialogs close
 * themselves with `window.history.back()` (see `useUrlEntityDialog`); a memory
 * history would let that call navigate the test page itself away. The starting
 * entry is pushed first so going back lands on the test page, never past it.
 */
export async function renderApp({ path }: RenderAppOptions) {
  window.history.pushState(null, '', path);

  const queryClient = createTestQueryClient();
  pendingQueryClients.push(queryClient);
  const router = createRouter({
    ...routerOptions,
    history: createBrowserHistory(),
  });

  const screen = await render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <SnackbarProvider>
          <RouterProvider router={router} />
        </SnackbarProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );

  return Object.assign(screen, { queryClient, router });
}
