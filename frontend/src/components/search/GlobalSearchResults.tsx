import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { GlobalSearchResultRow } from '@/components/search/GlobalSearchResultRow.tsx';
import {
  globalSearchRowDomId,
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
}: GlobalSearchResultsProps) => {
  if (isError) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="error">
          Search failed. Try again.
        </Typography>
      </Box>
    );
  }

  if (isFetching && rows.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (rows.length === 0) {
    return (
      <Box sx={{ p: 2 }}>
        <EmptyStateText>No matches</EmptyStateText>
      </Box>
    );
  }

  // Absent rather than pointing nowhere when the cursor is in the field: a
  // screen reader should not announce an active option that doesn't exist.
  const activeRow = activeIndex >= 0 ? rows[activeIndex] : undefined;

  return (
    <Box>
      {/* Old rows stay put while the next query runs; this is the only hint. */}
      {isFetching && <LinearProgress />}
      <List
        role="listbox"
        aria-label="Search results"
        aria-activedescendant={activeRow ? globalSearchRowDomId(activeRow) : undefined}
        disablePadding
      >
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
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', p: 1.5 }}>
          Showing top {MAX_GLOBAL_SEARCH_ROWS}
        </Typography>
      )}
    </Box>
  );
};
