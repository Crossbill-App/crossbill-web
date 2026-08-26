import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
      // A home-screen PWA is resumed, not reloaded, so a focus refetch is the
      // only thing that revalidates on reopening. Plain `true` defers to
      // staleTime and would skip it for the first five minutes.
      refetchOnWindowFocus: 'always',
    },
  },
});
