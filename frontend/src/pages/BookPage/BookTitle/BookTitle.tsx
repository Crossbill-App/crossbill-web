import type { BookDetails } from '@/api/generated/model';
import { BookCover } from '@/components/BookCover.tsx';
import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip.tsx';
import { ReadingStageChip } from '@/pages/BookPage/Reflection/ReadingStageChip.tsx';
import { ManageIcon } from '@/theme/Icons.tsx';
import { Box, LinearProgress, Tooltip, Typography } from '@mui/material';
import { useState } from 'react';
import { BookBlurb } from './BookBlurb.tsx';
import { BookEditDialog } from './BookEditDialog.tsx';
import { BookStatsStrip } from './BookStatsStrip.tsx';

export interface BookTitleProps {
  book: BookDetails;
}

export const BookTitle = ({ book }: BookTitleProps) => {
  const [editDialogOpen, setEditDialogOpen] = useState(false);

  const handleEdit = () => {
    setEditDialogOpen(true);
  };

  const progress =
    book.reading_position && book.end_position && book.end_position.index > 0
      ? Math.min(100, Math.round((book.reading_position.index / book.end_position.index) * 100))
      : 0;

  return (
    <>
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', lg: '280px 1fr 280px' },
          gap: 4,
          alignItems: 'stretch',
          mb: 2.5,
        }}
      >
        {/* Book Cover */}
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            alignSelf: 'start',
            width: '100%',
          }}
        >
          <Box
            sx={{
              flexShrink: 0,
              width: { xs: 160, md: 200 },
              height: { xs: 240, md: 280 },
            }}
          >
            <BookCover
              coverFile={book.cover_file ?? null}
              title={book.title}
              blurhash={book.cover_blurhash}
              height="100%"
              width="100%"
              objectFit="cover"
              sx={{
                boxShadow: 3,
                borderRadius: 1,
                transition: 'box-shadow 0.3s ease, transform 0.3s ease',
              }}
            />
          </Box>
          <Tooltip title={`${progress}% progress`} arrow>
            <LinearProgress
              variant="determinate"
              value={progress}
              sx={{ width: { xs: 160, md: 200 }, mt: 2, borderRadius: 1, height: 6 }}
            />
          </Tooltip>
          <ReadingStageChip bookId={book.id} readingStage={book.reading_stage ?? null} />
        </Box>

        {/* Book Info */}
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: { xs: 'center', lg: 'flex-start' },
            justifyContent: { xs: 'center', lg: 'flex-start' },
            textAlign: { xs: 'center', lg: 'left' },
            width: { xs: '100%', lg: 'auto' },
            position: 'relative',
          }}
        >
          <Typography variant="h1" component="h1" aria-label={book.title} sx={{ mb: 1 }}>
            {book.title}
            <IconButtonWithTooltip
              label="Manage book"
              onClick={handleEdit}
              icon={<ManageIcon />}
              size="small"
              sx={{
                color: 'text.primary',
                ml: 0.5,
                verticalAlign: 'middle',
                '& svg': { fontSize: '1.75rem' },
              }}
            />
          </Typography>

          <Typography
            variant="h2"
            sx={{
              color: 'primary.main',
              mb: { xs: 1, md: 2 },
              width: '100%',
            }}
            gutterBottom
          >
            {book.author || 'Unknown author'}
          </Typography>

          <BookBlurb description={book.description ?? null} />

          <BookStatsStrip book={book} />
        </Box>
      </Box>

      {/* Edit dialog */}
      <BookEditDialog book={book} open={editDialogOpen} onClose={() => setEditDialogOpen(false)} />
    </>
  );
};
