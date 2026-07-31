import { SnackbarProvider } from '@/context/SnackbarContext';
import { routeTree } from '@/routeTree.gen';
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
  const router = createRouter({
    routeTree,
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
