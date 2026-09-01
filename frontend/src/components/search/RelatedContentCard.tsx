import { BookCover } from '@/components/BookCover.tsx';
import { HoverableCardActionArea } from '@/components/cards/HoverableCardActionArea';
import {
  rowLinkProps,
  SEARCH_ROW_TYPE_LABELS,
  type GlobalSearchRow,
} from '@/components/search/globalSearchRows.ts';
import { clampToLines } from '@/utils/clampToLines.ts';
import { Box, Chip, Stack, Typography } from '@mui/material';
import { createLink } from '@tanstack/react-router';

const LinkCardActionArea = createLink(HoverableCardActionArea);

const CARD_WIDTH = { xs: 232, sm: 268 };

interface RelatedContentCardProps {
  row: GlobalSearchRow;
}

/**
 * One semantic match, sized for a carousel rather than a dropdown.
 *
 * Same information as `GlobalSearchResultRow` and reached through the same
 * `rowLinkProps`, but laid out vertically: a strip of these sits under content
 * the reader is already reading, where a few lines of the match are worth more
 * than the two a dropdown row can afford.
 */
export const RelatedContentCard = ({ row }: RelatedContentCardProps) => (
  <LinkCardActionArea
    {...rowLinkProps(row)}
    sx={{
      display: 'flex',
      alignItems: 'stretch',
      width: CARD_WIDTH,
      height: '100%',
      p: 2,
      bgcolor: 'background.paper',
      boxShadow: 1,
    }}
  >
    <Stack spacing={1} sx={{ width: '100%', minWidth: 0 }}>
      <Box>
        <Chip label={SEARCH_ROW_TYPE_LABELS[row.type]} variant="outlined" />
      </Box>

      {row.title && (
        <Typography variant="subtitle2" noWrap>
          {row.title}
        </Typography>
      )}

      <Typography variant="body2" sx={clampToLines(5)}>
        {row.text}
      </Typography>

      <Box sx={{ mt: 'auto', pt: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
        <BookCover
          coverFile={row.coverFile}
          blurhash={row.coverBlurhash}
          title={row.bookTitle}
          width={28}
          height={40}
          objectFit="cover"
          sx={{ borderRadius: 0.5, flexShrink: 0 }}
        />
        <Typography variant="caption" color="text.secondary" sx={clampToLines(2)}>
          {row.chapterLabel ? `${row.bookTitle} · ${row.chapterLabel}` : row.bookTitle}
        </Typography>
      </Box>
    </Stack>
  </LinkCardActionArea>
);
