import { useResetOnChange } from '@/hooks/useResetOnChange.ts';
import { Box, TextField, type SxProps, type Theme } from '@mui/material';
import { debounce } from 'lodash';
import { useEffect, useMemo, useState } from 'react';

interface SearchBarProps {
  onSearch: (searchText: string) => void;
  placeholder?: string;
  initialValue?: string;
  /**
   * `change` searches while typing, debounced — right for filtering data the
   * page already has. `submit` waits for Enter or blur, so an expensive search
   * runs once per finished query rather than once per keystroke.
   */
  commitOn?: 'change' | 'submit';
  /** Applied to the TextField, for callers on a non-default background. */
  sx?: SxProps<Theme>;
  /** Off by default: only a caller that owns the field's only focus target (e.g. a just-opened dialog) should set this. */
  autoFocus?: boolean;
  /** Extra attributes merged onto the native `<input>`, e.g. ARIA combobox
   *  wiring for a caller that owns a listbox of its own. Off by default. */
  slotProps?: { htmlInput?: React.InputHTMLAttributes<HTMLInputElement> };
}

export const SearchBar = ({
  onSearch,
  placeholder = 'Search...',
  initialValue = '',
  commitOn = 'change',
  sx,
  autoFocus = false,
  slotProps,
}: SearchBarProps) => {
  const [searchInput, setSearchInput] = useState(initialValue);

  const debouncedSearch = useMemo(
    () =>
      debounce((value: string) => {
        onSearch(value);
      }, 300),
    [onSearch]
  );

  // Update search input when initialValue changes (e.g., browser back/forward)
  useResetOnChange([initialValue], () => setSearchInput(initialValue));

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      debouncedSearch.cancel();
    };
  }, [debouncedSearch]);

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value;
    setSearchInput(value);
    if (commitOn === 'change') {
      debouncedSearch(value);
    }
  };

  const handleCommit = () => {
    if (commitOn === 'submit') {
      onSearch(searchInput);
    }
  };

  const handleClear = () => {
    debouncedSearch.cancel();
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
        onChange={handleChange}
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
              <Box
                component="span"
                // Keep the focus in the field: a blur here would commit the
                // text the click is about to throw away.
                onMouseDown={(e: React.MouseEvent) => e.preventDefault()}
                onClick={handleClear}
                sx={{
                  cursor: 'pointer',
                  color: 'text.secondary',
                  '&:hover': { color: 'text.primary' },
                }}
              >
                ✕
              </Box>
            ),
          },
          htmlInput: slotProps?.htmlInput,
        }}
      />
    </Box>
  );
};
