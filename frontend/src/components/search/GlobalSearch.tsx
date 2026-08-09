import { EmbeddingFeature } from '@/components/features/EmbeddingFeature.tsx';
import { GlobalSearchResults } from '@/components/search/GlobalSearchResults.tsx';
import { toGlobalSearchRows } from '@/components/search/globalSearchRows.ts';
import { SemanticSearchField } from '@/components/search/SemanticSearchField.tsx';
import { useSemanticSearch } from '@/components/search/useSemanticSearch.ts';
import { Box, Paper, Popper, type SxProps, type Theme } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';

/**
 * Not exported: the test restates the copy rather than importing it, matching
 * `StructurePage.test.tsx`, and knip fails CI on an export nothing imports.
 */
const GLOBAL_SEARCH_PLACEHOLDER = 'Search everything…';

/** The field sits on `primary.main`, where the default outlined look vanishes. */
const appBarFieldSx: SxProps<Theme> = (theme) => ({
  '& .MuiOutlinedInput-root': {
    backgroundColor: theme.customColors.whiteOverlay.light,
    color: theme.palette.primary.contrastText,
    '&:hover': { backgroundColor: theme.customColors.whiteOverlay.hover },
    '& .MuiOutlinedInput-notchedOutline': { borderColor: 'transparent' },
    '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: 'transparent' },
    '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
      borderColor: theme.palette.primary.contrastText,
      borderWidth: 1,
    },
  },
  '& .MuiInputBase-input': { py: 1 },
  '& .MuiInputBase-input::placeholder': {
    color: theme.palette.primary.contrastText,
    opacity: 0.7,
  },
});

/** Ten per type is enough to guarantee the true global top ten after merging. */
const RESULTS_PER_TYPE = 10;

/**
 * Semantic search over every book, in the app bar.
 *
 * The query lives here rather than in the URL: each route validates its own
 * search params, so a global `q` would mean editing every `validateSearch` and
 * navigating on every submit — a steep price for a dropdown of ten rows.
 */
export const GlobalSearch = () => {
  // State, not a ref: `anchorEl` and the width below are read during render,
  // and the lint rule for refs forbids reading `.current` there.
  const [anchorEl, setAnchorEl] = useState<HTMLDivElement | null>(null);
  const [query, setQuery] = useState('');
  // Closing keeps the query: the user scans the list, opens one hit, and comes
  // back for the next without retyping.
  const [isDismissed, setIsDismissed] = useState(false);

  const handleSearch = useCallback((value: string) => {
    setQuery(value);
    setIsDismissed(false);
  }, []);

  const { results, isFetching, isError, hasQuery } = useSemanticSearch({
    query,
    limit: RESULTS_PER_TYPE,
  });
  const rows = useMemo(() => toGlobalSearchRows(results), [results]);

  return (
    <EmbeddingFeature>
      <Box ref={setAnchorEl} sx={{ flexGrow: 1, maxWidth: 480, mx: 'auto' }}>
        <SemanticSearchField
          value={query}
          onChange={handleSearch}
          placeholder={GLOBAL_SEARCH_PLACEHOLDER}
          sx={appBarFieldSx}
        />
        <Popper
          open={hasQuery && !isDismissed}
          anchorEl={anchorEl}
          placement="bottom-start"
          sx={{ zIndex: (theme) => theme.zIndex.appBar + 1, width: anchorEl?.clientWidth }}
        >
          <Paper elevation={8} sx={{ mt: 1, maxHeight: 480, overflowY: 'auto' }}>
            <GlobalSearchResults
              rows={rows}
              isFetching={isFetching}
              isError={isError}
              activeIndex={-1}
              onSelect={() => setIsDismissed(true)}
            />
          </Paper>
        </Popper>
      </Box>
    </EmbeddingFeature>
  );
};
