import type { BookWithHighlightCount } from '@/api/generated/model';
import { Box } from '@mui/material';
import { AnimatePresence, motion } from 'motion/react';
import { BOOK_CARD_WIDTH, BookCard } from './BookCard.tsx';

export interface BookListProps {
  books: BookWithHighlightCount[];
  pageKey: string;
}

export const BookList = ({ books, pageKey }: BookListProps) => {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={pageKey}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
      >
        <Box
          sx={{
            display: 'grid',
            // Fixed rather than 1fr columns: the cards are intrinsically fixed
            // width, so stretching the cells only spreads slack between covers
            // that stay put anyway.
            gridTemplateColumns: `repeat(auto-fill, ${BOOK_CARD_WIDTH}px)`,
            gap: 4,
          }}
        >
          {books.map((book) => (
            <BookCard key={book.id} book={book} />
          ))}
        </Box>
      </motion.div>
    </AnimatePresence>
  );
};
