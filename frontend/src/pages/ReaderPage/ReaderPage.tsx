import { useGetBookDetails } from '@/api/generated/books/books.ts';
import { ReaderShell } from '@/components/reader/ReaderShell.tsx';
import { useNavigate, useParams } from '@tanstack/react-router';

/**
 * Reading a book in the browser, at `/book/{id}/read`.
 *
 * The page itself is thin on purpose: it turns the URL into a book, borrows
 * the title from the book-details query the book page has usually already
 * filled, and hands both to the reader. Everything else — the two credentials,
 * the navigator, the chrome — belongs to `ReaderShell`.
 */
export const ReaderPage = () => {
  const { bookId } = useParams({ strict: false });
  const navigate = useNavigate();
  const { data: book } = useGetBookDetails(Number(bookId));

  return (
    // Keyed by the book, so opening a different one gets a fresh navigator,
    // a fresh publication cookie and a fresh place in the text rather than
    // one book's reader being asked to become another's.
    <ReaderShell
      key={bookId}
      bookId={Number(bookId)}
      title={book?.title ?? ''}
      onClose={() => void navigate({ to: '/book/$bookId', params: { bookId: bookId! } })}
    />
  );
};
