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
});
