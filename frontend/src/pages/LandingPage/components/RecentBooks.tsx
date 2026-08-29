import { useGetRecentBooks } from '@/api/generated/books/books';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { Carousel } from '@/components/carousel/Carousel.tsx';
import { CarouselItem } from '@/components/carousel/CarouselItem.tsx';
import { PAGE_GUTTER } from '@/components/layout/Layouts.tsx';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { Alert, Box } from '@mui/material';
import { BookCard } from './BookCard';

const RECENT_BOOKS_LIMIT = 8;

/**
 * Matches the all-books grid from sm up; tighter on phones, where a 32px gap
 * would cost the row its second cover.
 */
const CAROUSEL_GAP = { xs: 2, sm: 4 };

/**
 * The landing page's row of covers for books the user last opened, or last
 * synced from an e-reader. One row rather than two: the same handful of books
 * tends to be both, and showing them twice said nothing extra.
 */
export const RecentBooks = () => {
  const { data, isLoading, isError } = useGetRecentBooks({ limit: RECENT_BOOKS_LIMIT });
  const books = data?.items;

  // Don't render the section at all when the query came back with no books
  if (!isLoading && !isError && (!books || books.length === 0)) {
    return null;
  }

  return (
    <Box sx={{ mb: 6 }}>
      <SectionTitle showDivider>Recent books</SectionTitle>

      {isLoading && <Spinner />}

      {isError && (
        <Box sx={{ py: 3 }}>
          <Alert severity="error">Failed to load recent books.</Alert>
        </Box>
      )}

      {books && books.length > 0 && (
        <Carousel aria-label="Recent books" gap={CAROUSEL_GAP} bleed={PAGE_GUTTER}>
          {books.map((book) => (
            <CarouselItem key={book.id}>
              <BookCard book={book} />
            </CarouselItem>
          ))}
        </Carousel>
      )}
    </Box>
  );
};
