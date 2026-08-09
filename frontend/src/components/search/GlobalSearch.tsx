import { EmbeddingFeature } from '@/components/features/EmbeddingFeature.tsx';
import { SemanticSearchField } from '@/components/search/SemanticSearchField.tsx';
import { Box, type SxProps, type Theme } from '@mui/material';
import { useCallback, useState } from 'react';

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

/**
 * Semantic search over every book, in the app bar.
 *
 * The query lives here rather than in the URL: each route validates its own
 * search params, so a global `q` would mean editing every `validateSearch` and
 * navigating on every submit — a steep price for a dropdown of ten rows.
 */
export const GlobalSearch = () => {
  const [query, setQuery] = useState('');
  const handleSearch = useCallback((value: string) => setQuery(value), []);

  return (
    <EmbeddingFeature>
      <Box sx={{ flexGrow: 1, maxWidth: 480, mx: 'auto' }}>
        <SemanticSearchField
          value={query}
          onChange={handleSearch}
          placeholder={GLOBAL_SEARCH_PLACEHOLDER}
          sx={appBarFieldSx}
        />
      </Box>
    </EmbeddingFeature>
  );
};
