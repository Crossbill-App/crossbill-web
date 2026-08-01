import { useGetRecentlyViewedBooks } from '@/api/generated/books/books';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { Carousel } from '@/components/carousel/Carousel.tsx';
import { CarouselItem } from '@/components/carousel/CarouselItem.tsx';
import { PAGE_GUTTER } from '@/components/layout/Layouts.tsx';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { Alert, Box } from '@mui/material';
import { BookCard } from './BookCard';

const RECENTLY_VIEWED_LIMIT = 8;

/**
 * Matches the all-books grid from sm up; tighter on phones, where a 32px gap
 * would cost the row its second cover.
 */
const CAROUSEL_GAP = { xs: 2, sm: 4 };

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
        <Carousel aria-label="Recently viewed books" gap={CAROUSEL_GAP} bleed={PAGE_GUTTER}>
          {data.items.map((book) => (
            <CarouselItem key={book.id}>
              <BookCard book={book} />
            </CarouselItem>
          ))}
        </Carousel>
      )}
    </Box>
  );
};
