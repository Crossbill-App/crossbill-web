import { useGetRecentBooks } from '@/api/generated/books/books';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { BOOK_CARD_WIDTH, BookCard } from '@/components/books/BookCard.tsx';
import { Carousel } from '@/components/carousel/Carousel.tsx';
import { CarouselItem } from '@/components/carousel/CarouselItem.tsx';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { PAGE_GUTTER } from '@/components/layout/Layouts.tsx';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { Alert, Box } from '@mui/material';

const RECENT_BOOKS_LIMIT = 8;

/**
 * Matches the all-books grid from sm up; tighter on phones, where a 32px gap
 * would cost the row its second cover.
 */
const CAROUSEL_GAP = { xs: 2, sm: 4 };

/** `CAROUSEL_GAP.sm` in pixels, at MUI's 8px spacing unit. */
const CAROUSEL_GAP_PX = CAROUSEL_GAP.sm * 8;

/**
 * How wide the row of covers runs once every cover of it is on screen. The
 * activity band below is capped at the same width so the two rows end together.
 */
export const RECENT_ROW_WIDTH =
  RECENT_BOOKS_LIMIT * BOOK_CARD_WIDTH + (RECENT_BOOKS_LIMIT - 1) * CAROUSEL_GAP_PX;

/**
 * The landing page's row of covers for books the user last opened, or last
 * synced from an e-reader. One row rather than two: the same handful of books
 * tends to be both, and showing them twice said nothing extra.
 *
 * A reader with no books keeps the section and is told what fills it, rather
 * than meeting a dashboard with a heading missing from it.
 */
export const RecentBooks = () => {
  const { data, isLoading, isError } = useGetRecentBooks({ limit: RECENT_BOOKS_LIMIT });
  const books = data?.items;
  const empty = !isLoading && !isError && !books?.length;

  return (
    <Box sx={{ mb: 6 }}>
      <SectionTitle showDivider>Recent books</SectionTitle>

      {isLoading && <Spinner />}

      {isError && (
        <Box sx={{ py: 3 }}>
          <Alert severity="error">Failed to load recent books.</Alert>
        </Box>
      )}

      {empty && (
        <EmptyStateText>
          No books yet. Upload highlights from your e-reader to get started.
        </EmptyStateText>
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
