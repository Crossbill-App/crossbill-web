import { useResetOnChange } from '@/hooks/useResetOnChange.ts';
import { Box, TextField } from '@mui/material';
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
}

export const SearchBar = ({
  onSearch,
  placeholder = 'Search...',
  initialValue = '',
  commitOn = 'change',
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
        placeholder={placeholder}
        value={searchInput}
        onChange={handleChange}
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
        }}
      />
    </Box>
  );
};
