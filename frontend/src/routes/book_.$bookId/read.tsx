import { ReaderPage } from '@/pages/ReaderPage/ReaderPage.tsx';
import { createFileRoute } from '@tanstack/react-router';

// `book_` keeps this a sibling of `/book/$bookId` rather than a child, so the
// reader gets the whole viewport instead of the book page's layout.
export const Route = createFileRoute('/book_/$bookId/read')({
  component: ReaderPage,
});
