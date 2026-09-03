import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { GLOBAL_SEARCH_INSET_X } from '@/components/search/globalSearchLayout.ts';
import { GlobalSearchResultRow } from '@/components/search/GlobalSearchResultRow.tsx';
import {
  MAX_GLOBAL_SEARCH_ROWS,
  type GlobalSearchRow,
} from '@/components/search/globalSearchRows.ts';
import { Box, CircularProgress, LinearProgress, List, Typography } from '@mui/material';

interface GlobalSearchResultsProps {
  rows: GlobalSearchRow[];
  isFetching: boolean;
  isError: boolean;
  /** Index of the keyboard cursor, or -1 when the cursor is in the field. */
  activeIndex: number;
  onSelect: () => void;
  /** DOM id for the listbox `<ul>`, matching the field's `aria-controls`. */
  listboxId: string;
}

/**
 * The dropdown's body, shared by the desktop popper and the mobile dialog.
 *
 * Renders only when there is a query, so "nothing matched" and "no search yet"
 * never have to be told apart here — the caller decides whether to mount it.
 */
export const GlobalSearchResults = ({
  rows,
  isFetching,
  isError,
  activeIndex,
  onSelect,
  listboxId,
}: GlobalSearchResultsProps) => {
  if (isError) {
    return (
      <Box sx={{ px: GLOBAL_SEARCH_INSET_X, py: 2.5 }}>
        <Typography variant="body2" color="error">
          Search failed. Try again.
        </Typography>
      </Box>
    );
  }

  if (isFetching && rows.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress size={24} aria-label="Searching" />
      </Box>
    );
  }

  if (rows.length === 0) {
    return (
      <Box sx={{ px: GLOBAL_SEARCH_INSET_X, py: 2.5 }}>
        <EmptyStateText>No matches</EmptyStateText>
      </Box>
    );
  }

  return (
    <Box>
      {/* Old rows stay put while the next query runs; this is the only hint. */}
      {isFetching && <LinearProgress />}
      <List id={listboxId} role="listbox" aria-label="Search results" disablePadding>
        {rows.map((row, index) => (
          <GlobalSearchResultRow
            key={row.key}
            row={row}
            isActive={index === activeIndex}
            onSelect={onSelect}
          />
        ))}
      </List>
      {rows.length === MAX_GLOBAL_SEARCH_ROWS && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', px: GLOBAL_SEARCH_INSET_X, py: 2 }}
        >
          Showing top {MAX_GLOBAL_SEARCH_ROWS}
        </Typography>
      )}
    </Box>
  );
};
