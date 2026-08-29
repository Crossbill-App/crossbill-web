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

/** Inset of the markers that sit on top of the cover, on every edge. */
const COVER_INSET = 8;

export interface BookCardProps {
  book: BookWithHighlightCount;
}

/**
 * What the reader has made of the book, as a strip across the foot of the
 * cover. Each count is dropped at zero, and a book nobody has marked up carries
 * no strip at all rather than an empty one.
 *
 * The scrim is what makes it legible: cover art comes in every shade, so the
 * counts need a darkened surface of their own to sit on.
 */
const BookCounts = ({ book }: BookCardProps) => {
  const counts = [
    { icon: HighlightsIcon, count: book.highlight_count, noun: 'highlight' },
    { icon: NotesIcon, count: book.note_count ?? 0, noun: 'note' },
    { icon: FlashcardsIcon, count: book.flashcard_count ?? 0, noun: 'flashcard' },
  ];

  if (counts.every(({ count }) => count === 0)) return null;

  return (
    <Box
      // The strip has no accessible name of its own -- an aria-label here would
      // only pad the link's. This is how a test sees whether it rendered.
      data-testid="book-counts"
      sx={(theme) => ({
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 1,
        py: 0.5,
        backgroundColor: theme.customColors.coverScrim.strip,
        color: theme.palette.common.white,
        typography: 'caption',
        borderBottomLeftRadius: theme.shape.borderRadius,
        borderBottomRightRadius: theme.shape.borderRadius,
      })}
    >
      {counts.map(({ icon, count, noun }) => (
        <CountWithIcon key={noun} icon={icon} count={count} noun={noun} />
      ))}
    </Box>
  );
};

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
            <Box sx={{ position: 'absolute', top: COVER_INSET, right: COVER_INSET }}>
              <ReadingStageIcon stage={book.reading_stage} />
            </Box>

            <BookCounts book={book} />
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
        </Box>
      </Link>
    </FadeInOut>
  );
};
