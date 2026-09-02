import { BookCover } from '@/components/BookCover.tsx';
import { MetadataRow } from '@/components/cards/MetadataRow.tsx';
import {
  globalSearchRowDomId,
  rowLinkProps,
  SEARCH_ROW_TYPE_LABELS,
  type GlobalSearchRow,
} from '@/components/search/globalSearchRows.ts';
import { clampToLines } from '@/utils/clampToLines.ts';
import { Box, Chip, ListItemButton, Stack, Typography } from '@mui/material';
import { createLink } from '@tanstack/react-router';

/**
 * MUI's `ListItemButton` injects an `href` prop when given `component={Link}`
 * directly (it copies `to` to `href` for anchor semantics). TanStack Router's
 * `Link` then treats that injected `href` as authoritative and re-parses
 * `search` off its (empty) query string, silently dropping the real search
 * params. `createLink` wires the component in the way the router expects,
 * without that collision.
 */
const LinkListItemButton = createLink(ListItemButton);

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
    sx={{ alignItems: 'center', gap: 1.5, py: 1.5, display: 'flex' }}
  >
    <BookCover
      coverFile={row.coverFile}
      blurhash={row.coverBlurhash}
      title={row.bookTitle}
      width={52}
      height={72}
      objectFit="cover"
      sx={{ borderRadius: 0.5, flexShrink: 0 }}
    />
    <Stack sx={{ minWidth: 0 }} spacing={0.25}>
      {row.title && (
        <Typography variant="subtitle2" noWrap>
          {row.title}
        </Typography>
      )}
      <Box sx={{ gap: 1, display: 'flex', alignItems: 'center' }}>
        <Chip label={SEARCH_ROW_TYPE_LABELS[row.type]} variant="outlined" />
        <MetadataRow variant="caption" noWrap items={[row.bookTitle, row.chapterLabel]} />
      </Box>
      <Typography variant="body1" sx={clampToLines(2)}>
        {row.text}
      </Typography>
    </Stack>
  </LinkListItemButton>
);
