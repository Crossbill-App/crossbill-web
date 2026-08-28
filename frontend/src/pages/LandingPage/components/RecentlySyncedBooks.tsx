import { useGetRecentlySyncedBooks } from '@/api/generated/books/books';
import { BookCarouselSection } from './BookCarouselSection';

const RECENTLY_SYNCED_LIMIT = 8;

export const RecentlySyncedBooks = () => {
  const { data, isLoading, isError } = useGetRecentlySyncedBooks({
    limit: RECENTLY_SYNCED_LIMIT,
  });

  return (
    <BookCarouselSection
      title="Recently synced"
      ariaLabel="Recently synced books"
      books={data?.items}
      isLoading={isLoading}
      isError={isError}
      errorText="Failed to load recently synced books."
    />
  );
};
