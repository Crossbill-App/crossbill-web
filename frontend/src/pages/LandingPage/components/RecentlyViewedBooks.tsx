import { useGetRecentlyViewedBooks } from '@/api/generated/books/books';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { Alert, Box } from '@mui/material';
import { BookList } from './BookList';

const RECENTLY_VIEWED_LIMIT = 8;

export const RecentlyViewedBooks = () => {
  const { data, isLoading, isError } = useGetRecentlyViewedBooks({
    limit: RECENTLY_VIEWED_LIMIT,
  });

  // Don't render the section if there are no recently viewed books
  if (!isLoading && !isError && (!data?.items || data.items.length === 0)) {
    return null;
  }

  return (
    <Box sx={{ mb: 6 }}>
      <SectionTitle showDivider>Recently Viewed</SectionTitle>

      {isLoading && <Spinner />}

      {isError && (
        <Box sx={{ py: 3 }}>
          <Alert severity="error">Failed to load recently viewed books.</Alert>
        </Box>
      )}

      {data?.items && data.items.length > 0 && (
        <BookList books={data.items} pageKey="recently-viewed" />
      )}
    </Box>
  );
};
