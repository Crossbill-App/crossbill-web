import { BookCover } from '@/components/BookCover.tsx';
import type { GlobalSearchRow } from '@/components/search/globalSearchRows.ts';
import { Box, Chip, ListItemButton, Stack, Typography } from '@mui/material';
import { createLink, linkOptions } from '@tanstack/react-router';

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

/**
 * Router props for a row, as a switch rather than strings on the row itself:
 * TanStack Router types `to` against the route tree, and a `to: string` field
 * would throw that away.
 *
 * Left un-exported until Task 6 imports it — knip fails CI on an export nothing
 * references yet.
 */
const rowLinkProps = (row: GlobalSearchRow) => {
  const params = { bookId: String(row.bookId) };
  switch (row.type) {
    case 'highlight':
      return linkOptions({
        to: '/book/$bookId/highlights',
        params,
        search: { highlightId: row.id },
      });
    case 'note':
      return linkOptions({ to: '/book/$bookId/notes', params, search: { noteId: row.id } });
    case 'chapter':
      return linkOptions({
        to: '/book/$bookId/structure',
        params,
        search: { chapterId: row.id },
      });
  }
};

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
    id={`global-search-${row.key}`}
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
