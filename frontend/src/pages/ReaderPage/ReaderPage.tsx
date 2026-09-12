import { useGetBookDetails } from '@/api/generated/books/books.ts';
import { ReaderShell } from '@/components/reader/ReaderShell.tsx';
import { useNavigate, useParams } from '@tanstack/react-router';

export const ReaderPage = () => {
  const { bookId } = useParams({ strict: false });
  const navigate = useNavigate();
  const { data: book } = useGetBookDetails(Number(bookId));

  return (
    <ReaderShell
      title={book?.title ?? ''}
      onClose={() => void navigate({ to: '/book/$bookId', params: { bookId: String(bookId) } })}
    />
  );
};
