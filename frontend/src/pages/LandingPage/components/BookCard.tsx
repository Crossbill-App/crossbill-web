import type { BookWithHighlightCount } from '@/api/generated/model';
import { FadeInOut } from '@/components/animations/FadeInOut.tsx';
import { BookCover } from '@/components/BookCover';
import { CountWithIcon } from '@/components/CountWithIcon.tsx';
import { ReadingStageIcon } from '@/components/readingStage/ReadingStageIcon.tsx';
import { FlashcardsIcon, HighlightsIcon, NotesIcon } from '@/theme/Icons.tsx';
import { Box, Typography } from '@mui/material';
import { Link } from '@tanstack/react-router';

/** Cover width, and therefore the card's width. Grids that lay these out
 *  need the same number to size their columns. */
export const BOOK_CARD_WIDTH = 150;

export interface BookCardProps {
  book: BookWithHighlightCount;
}

/**
 * What the reader has made of the book: highlights, notes, cards. Each count
 * is dropped at zero, so a book nobody has marked up carries no row at all.
 */
const BookCounts = ({ book }: BookCardProps) => (
  <Box
    sx={{
      display: 'flex',
      flexWrap: 'wrap',
      alignItems: 'center',
      gap: 1,
      mt: 0.5,
      maxWidth: BOOK_CARD_WIDTH,
      color: 'text.secondary',
      typography: 'caption',
    }}
  >
    <CountWithIcon icon={HighlightsIcon} count={book.highlight_count} noun="highlight" />
    <CountWithIcon icon={NotesIcon} count={book.note_count ?? 0} noun="note" />
    <CountWithIcon icon={FlashcardsIcon} count={book.flashcard_count ?? 0} noun="flashcard" />
  </Box>
);

const truncateText = (text: string, maxLength: number) => {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '...';
};

export const BookCard = ({ book }: BookCardProps) => {
  return (
    <FadeInOut ekey={book.id}>
      <Link
        to="/book/$bookId"
        params={{ bookId: String(book.id) }}
        style={{ textDecoration: 'none', color: 'inherit', display: 'inline-block' }}
      >
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            width: 'fit-content',
            transition: 'transform 0.3s ease',
            '&:hover': {
              transform: 'translateY(-4px)',
              '& .book-cover': {
                boxShadow: 4,
              },
            },
          }}
        >
          <Box sx={{ position: 'relative', width: 'fit-content' }}>
            <BookCover
              coverFile={book.cover_file ?? null}
              title={book.title}
              blurhash={book.cover_blurhash}
              width={BOOK_CARD_WIDTH}
              height={220}
              objectFit="cover"
              sx={{
                boxShadow: 3,
                borderRadius: 1,
                transition: 'box-shadow 0.3s ease',
              }}
            />

            {/* Reading stage marker */}
            <Box sx={{ position: 'absolute', top: 8, right: 8 }}>
              <ReadingStageIcon stage={book.reading_stage} />
            </Box>
          </Box>

          {/* Book title */}
          <Typography
            variant="body1"
            component="h3"
            sx={{
              fontWeight: 600,
              color: 'text.primary',
              mt: 1.5,
              maxWidth: BOOK_CARD_WIDTH,
            }}
            title={book.title}
          >
            {truncateText(book.title, 50)}
          </Typography>

          {/* Book author */}
          <Typography
            variant="body2"
            title={book.author || 'Unknown author'}
            sx={{
              color: 'text.secondary',
              maxWidth: BOOK_CARD_WIDTH,
              mt: 0.5,
            }}
          >
            {truncateText(book.author || 'Unknown author', 30)}
          </Typography>

          <BookCounts book={book} />
        </Box>
      </Link>
    </FadeInOut>
  );
};
