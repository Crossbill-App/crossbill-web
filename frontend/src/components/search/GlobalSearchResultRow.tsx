import { BookCover } from '@/components/BookCover.tsx';
import { MetadataRow } from '@/components/cards/MetadataRow.tsx';
import { GLOBAL_SEARCH_INSET_X } from '@/components/search/globalSearchLayout.ts';
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
    sx={{ alignItems: 'center', gap: 2, px: GLOBAL_SEARCH_INSET_X, py: 2, display: 'flex' }}
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
    <Stack sx={{ minWidth: 0 }} spacing={0.75}>
      {row.title && (
        <Typography variant="subtitle2" noWrap>
          {row.title}
        </Typography>
      )}
      <Box sx={{ gap: 1, display: 'flex', alignItems: 'center' }}>
        <Chip label={SEARCH_ROW_TYPE_LABELS[row.type]} variant="outlined" />
        {/* A book row's title line is already the book title; repeating it
            below would leave only the author saying anything new. */}
        <MetadataRow
          variant="caption"
          noWrap
          items={row.type === 'book' ? [row.chapterLabel] : [row.bookTitle, row.chapterLabel]}
        />
      </Box>
      {row.text && (
        <Typography variant="body1" sx={clampToLines(2)}>
          {row.text}
        </Typography>
      )}
    </Stack>
  </LinkListItemButton>
);
