import { useGetRecentlySyncedBooks } from '@/api/generated/books/books';
import { BookCarouselSection } from './BookCarouselSection';

const RECENTLY_SYNCED_LIMIT = 8;

export const RecentlySyncedBooks = () => {
  const { data, isLoading, isError } = useGetRecentlySyncedBooks({
    limit: RECENTLY_SYNCED_LIMIT,
  });

  return (
    <BookCarouselSection
      title="Recently read"
      ariaLabel="Recently read books"
      books={data?.items}
      isLoading={isLoading}
      isError={isError}
      errorText="Failed to load recently read books."
    />
  );
};
