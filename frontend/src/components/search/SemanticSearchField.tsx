import { EmbeddingFeature } from '@/components/features/EmbeddingFeature.tsx';
import { SearchBar } from '@/components/inputs/SearchBar.tsx';
import { Box, type SxProps, type Theme } from '@mui/material';

interface SemanticSearchFieldProps {
  value: string;
  /** Called with the submitted query text. Must be a stable callback. */
  onChange: (value: string) => void;
  placeholder: string;
  /** Applied to the input, for callers on a non-default background. */
  sx?: SxProps<Theme>;
  /** Off by default: only a caller that owns the field's only focus target (e.g. a just-opened dialog) should set this. */
  autoFocus?: boolean;
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
export const SemanticSearchField = ({
  value,
  onChange,
  placeholder,
  sx,
  autoFocus,
}: SemanticSearchFieldProps) => (
  <EmbeddingFeature>
    <Box>
      <SearchBar
        onSearch={onChange}
        placeholder={placeholder}
        initialValue={value}
        commitOn="submit"
        sx={sx}
        autoFocus={autoFocus}
      />
    </Box>
  </EmbeddingFeature>
);
