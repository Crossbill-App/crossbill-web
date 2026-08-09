import { BookCover } from '@/components/BookCover.tsx';
import {
  globalSearchRowDomId,
  rowLinkProps,
  type GlobalSearchRow,
} from '@/components/search/globalSearchRows.ts';
import { Box, Chip, ListItemButton, Stack, Typography } from '@mui/material';
import { createLink } from '@tanstack/react-router';

const CHIP_LABELS: Record<GlobalSearchRow['type'], string> = {
  highlight: 'Highlight',
  note: 'Note',
  chapter: 'Chapter',
};

/**
 * MUI's `ListItemButton` injects an `href` prop when given `component={Link}`
 * directly (it copies `to` to `href` for anchor semantics). TanStack Router's
 * `Link` then treats that injected `href` as authoritative and re-parses
 * `search` off its (empty) query string, silently dropping the real search
 * params. `createLink` wires the component in the way the router expects,
 * without that collision.
 */
const LinkListItemButton = createLink(ListItemButton);

/** Two lines of matched text, clamped rather than truncated in JS. */
const clampToTwoLines = {
  display: '-webkit-box',
  WebkitLineClamp: 2,
  WebkitBoxOrient: 'vertical' as const,
  overflow: 'hidden',
};

interface GlobalSearchResultRowProps {
  row: GlobalSearchRow;
  /** Keyboard cursor position, not selection — the row is never checked. */
  isActive: boolean;
  onSelect: () => void;
}

export const GlobalSearchResultRow = ({ row, isActive, onSelect }: GlobalSearchResultRowProps) => (
  <LinkListItemButton
    {...rowLinkProps(row)}
    id={globalSearchRowDomId(row)}
    role="option"
    aria-selected={isActive}
    selected={isActive}
    onClick={onSelect}
    sx={{ alignItems: 'flex-start', gap: 1.5, py: 1.5 }}
  >
    <BookCover
      coverFile={row.coverFile}
      blurhash={row.coverBlurhash}
      title={row.bookTitle}
      width={40}
      height={56}
      objectFit="cover"
      sx={{ borderRadius: 1, flexShrink: 0 }}
    />
    <Stack sx={{ minWidth: 0 }} spacing={0.25}>
      <Box>
        <Chip label={CHIP_LABELS[row.type]} size="small" variant="outlined" />
      </Box>
      {row.title && (
        <Typography variant="subtitle2" noWrap>
          {row.title}
        </Typography>
      )}
      <Typography variant="body2" sx={clampToTwoLines}>
        {row.text}
      </Typography>
      <Typography variant="caption" color="text.secondary" noWrap>
        {row.chapterLabel ? `${row.bookTitle} · ${row.chapterLabel}` : row.bookTitle}
      </Typography>
    </Stack>
  </LinkListItemButton>
);
