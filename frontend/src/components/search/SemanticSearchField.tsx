import { EmbeddingFeature } from '@/components/features/EmbeddingFeature.tsx';
import { SearchBar } from '@/components/inputs/SearchBar.tsx';
import { Box } from '@mui/material';

interface SemanticSearchFieldProps {
  value: string;
  /** Called with the submitted query text. Must be a stable callback. */
  onChange: (value: string) => void;
  placeholder: string;
}

/**
 * Natural-language search box, hidden when embeddings are off. The query is
 * submitted on Enter or blur, never per keystroke: each search is an embedding
 * call, so half-typed queries are not worth running.
 *
 * Deliberately dumb: it renders the input and knows
 * nothing about results. Callers pair it with `useSemanticSearch` and decide
 * what a match means.
 */
export const SemanticSearchField = ({ value, onChange, placeholder }: SemanticSearchFieldProps) => (
  <EmbeddingFeature>
    <Box>
      <SearchBar
        onSearch={onChange}
        placeholder={placeholder}
        initialValue={value}
        commitOn="submit"
      />
    </Box>
  </EmbeddingFeature>
);
