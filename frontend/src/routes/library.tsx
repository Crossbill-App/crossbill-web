import { LibraryPage } from '@/pages/LibraryPage/LibraryPage';
import { createFileRoute } from '@tanstack/react-router';

export type LibrarySearch = {
  search?: string;
  page?: number;
};

export const Route = createFileRoute('/library')({
  component: LibraryPage,
  validateSearch: (search: Record<string, unknown>): LibrarySearch => {
    return {
      search: (search.search as string | undefined) || undefined,
      page: Number(search.page) || 1,
    };
  },
});
