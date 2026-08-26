import { useGetRecentlyViewedBooks } from '@/api/generated/books/books';
import { BookCarouselSection } from './BookCarouselSection';

const RECENTLY_VIEWED_LIMIT = 8;

export const RecentlyViewedBooks = () => {
  const { data, isLoading, isError } = useGetRecentlyViewedBooks({
    limit: RECENTLY_VIEWED_LIMIT,
  });

  return (
    <BookCarouselSection
      title="Recently Viewed"
      ariaLabel="Recently viewed books"
      books={data?.items}
      isLoading={isLoading}
      isError={isError}
      errorText="Failed to load recently viewed books."
    />
  );
};
