import { useGetBookDetails } from '@/api/generated/books/books.ts';
import { ReaderShell } from '@/components/reader/ReaderShell.tsx';
import { useNavigate, useParams } from '@tanstack/react-router';
import { useMemo } from 'react';

export const ReaderPage = () => {
  const { bookId } = useParams({ strict: false });
  const navigate = useNavigate();
  const { data: book } = useGetBookDetails(Number(bookId));
  // A new array every render would be a new set of decorations every render.
  const highlights = useMemo(() => book?.chapters.flatMap((chapter) => chapter.highlights), [book]);

  return (
    <ReaderShell
      key={bookId}
      bookId={Number(bookId)}
      title={book?.title ?? ''}
      highlights={highlights}
      onClose={() => void navigate({ to: '/book/$bookId', params: { bookId: String(bookId) } })}
    />
  );
};
