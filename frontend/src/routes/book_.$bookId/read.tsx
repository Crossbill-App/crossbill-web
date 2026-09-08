import { ReaderPage } from '@/pages/ReaderPage/ReaderPage.tsx';
import { createFileRoute } from '@tanstack/react-router';

/**
 * The `book_` prefix is what keeps the reader out of the book page's own
 * layout: the URL still reads as one of the book's pages, but the route is a
 * sibling of `/book/$bookId` rather than a child, so the reader gets the whole
 * viewport instead of a column between the tab rail and the right rail.
 */
export const Route = createFileRoute('/book_/$bookId/read')({
  component: ReaderPage,
  // The same param the book page's highlight list opens its dialog with, so a
  // highlight tapped on the page is a place in history and a link that can be
  // pasted — and the back button closes the dialog rather than the book.
  validateSearch: (search: Record<string, unknown>): { highlightId?: number } => ({
    highlightId: (search.highlightId as number | undefined) || undefined,
  }),
});
