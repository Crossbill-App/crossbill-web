import { LandingPage } from '@/pages/LandingPage/LandingPage';
import type { LibrarySearch } from '@/routes/library';
import { createFileRoute, redirect } from '@tanstack/react-router';

export const Route = createFileRoute('/')({
  component: LandingPage,
  /**
   * The all-books list used to live here, so `/?search=…&page=…` is a link a
   * reader may have bookmarked or shared. Accept those params and hand them to
   * the library rather than dropping the reader on a dashboard that ignores
   * them. Nothing on this page reads them.
   */
  validateSearch: (search: Record<string, unknown>): LibrarySearch => {
    return {
      search: (search.search as string | undefined) || undefined,
      page: Number(search.page) || undefined,
    };
  },
  beforeLoad: ({ search }) => {
    if (search.search || (search.page && search.page > 1)) {
      throw redirect({ to: '/library', search: { search: search.search, page: search.page } });
    }
  },
});
