import { SearchBar } from '@/components/inputs/SearchBar.tsx';
import { Box, type SxProps, type Theme } from '@mui/material';

interface ContentSearchFieldProps {
  value: string;
  /** Called with the submitted query text. Must be a stable callback. */
  onChange: (value: string) => void;
  placeholder: string;
  /** Applied to the input, for callers on a non-default background. */
  sx?: SxProps<Theme>;
  /** Off by default: only a caller that owns the field's only focus target (e.g. a just-opened dialog) should set this. */
  autoFocus?: boolean;
  /** Extra attributes merged onto the native `<input>`, e.g. ARIA combobox
   *  wiring for a caller that owns a listbox of its own. */
  slotProps?: { htmlInput?: React.InputHTMLAttributes<HTMLInputElement> };
}

/**
 * Search box for `useContentSearch`. Commit timing is `SearchBar`'s, shared
 * with every other search field: Enter or blur, never per keystroke — which
 * also keeps half-typed queries out of the embedding calls.
 *
 * Deliberately dumb: it renders the input and knows nothing about results or
 * about which features the server has. A caller whose search needs embeddings
 * wraps it in `EmbeddingFeature` itself.
 */
export const ContentSearchField = ({
  value,
  onChange,
  placeholder,
  sx,
  autoFocus,
  slotProps,
}: ContentSearchFieldProps) => (
  <Box>
    <SearchBar
      onSearch={onChange}
      placeholder={placeholder}
      initialValue={value}
      sx={sx}
      autoFocus={autoFocus}
      slotProps={slotProps}
    />
  </Box>
);
