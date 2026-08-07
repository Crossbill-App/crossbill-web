import { EmbeddingFeature } from '@/components/features/EmbeddingFeature.tsx';
import { SearchBar } from '@/components/inputs/SearchBar.tsx';
import { Box, LinearProgress } from '@mui/material';

interface SemanticSearchFieldProps {
  value: string;
  /** Called with the debounced query text. Must be a stable callback. */
  onChange: (value: string) => void;
  placeholder: string;
  isFetching?: boolean;
}

/**
 * Debounced natural-language search box, hidden when embeddings are off.
 *
 * Deliberately dumb: it renders the input and a progress hairline, and knows
 * nothing about results. Callers pair it with `useSemanticSearch` and decide
 * what a match means.
 */
export const SemanticSearchField = ({
  value,
  onChange,
  placeholder,
  isFetching = false,
}: SemanticSearchFieldProps) => (
  <EmbeddingFeature>
    <Box>
      <SearchBar onSearch={onChange} placeholder={placeholder} initialValue={value} />
      {isFetching && <LinearProgress sx={{ height: 2, borderRadius: 1 }} />}
    </Box>
  </EmbeddingFeature>
);
