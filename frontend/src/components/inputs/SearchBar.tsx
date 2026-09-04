import { useResetOnChange } from '@/hooks/useResetOnChange.ts';
import { CloseIcon } from '@/theme/Icons.tsx';
import { Box, IconButton, TextField, type SxProps, type Theme } from '@mui/material';
import { useState } from 'react';

interface SearchBarProps {
  /**
   * Called with the committed query — on Enter, on blur, and on a clear.
   * Never per keystroke, so it may run an expensive search.
   */
  onSearch: (searchText: string) => void;
  placeholder?: string;
  initialValue?: string;
  /** Applied to the TextField, for callers on a non-default background. */
  sx?: SxProps<Theme>;
  /** Off by default: only a caller that owns the field's only focus target (e.g. a just-opened dialog) should set this. */
  autoFocus?: boolean;
  /** Extra attributes merged onto the native `<input>`, e.g. ARIA combobox
   *  wiring for a caller that owns a listbox of its own. Off by default. */
  slotProps?: { htmlInput?: React.InputHTMLAttributes<HTMLInputElement> };
}

/**
 * The one search field in the app. Every search box commits the same way —
 * Enter or blur — whatever engine sits behind it, so two tabs apart cannot
 * behave differently. Typing changes nothing until the query is finished.
 */
export const SearchBar = ({
  onSearch,
  placeholder = 'Search...',
  initialValue = '',
  sx,
  autoFocus = false,
  slotProps,
}: SearchBarProps) => {
  const [searchInput, setSearchInput] = useState(initialValue);

  // Update search input when initialValue changes (e.g., browser back/forward)
  useResetOnChange([initialValue], () => setSearchInput(initialValue));

  const handleCommit = () => {
    onSearch(searchInput);
  };

  const handleClear = () => {
    setSearchInput('');
    onSearch('');
  };

  return (
    <Box>
      <TextField
        fullWidth
        autoFocus={autoFocus}
        placeholder={placeholder}
        value={searchInput}
        onChange={(event) => setSearchInput(event.target.value)}
        sx={sx}
        onBlur={handleCommit}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            handleClear();
          }
          if (e.key === 'Enter') {
            handleCommit();
          }
        }}
        slotProps={{
          input: {
            endAdornment: searchInput && (
              <IconButton
                size="small"
                aria-label="Clear search"
                // Keep the focus in the field: a blur here would commit the
                // text the click is about to throw away.
                onMouseDown={(e: React.MouseEvent) => e.preventDefault()}
                onClick={handleClear}
                sx={{ color: 'text.secondary', '&:hover': { color: 'text.primary' } }}
              >
                <CloseIcon fontSize="small" />
              </IconButton>
            ),
          },
          htmlInput: slotProps?.htmlInput,
        }}
      />
    </Box>
  );
};
