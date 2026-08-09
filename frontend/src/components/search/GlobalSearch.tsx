import { EmbeddingFeature } from '@/components/features/EmbeddingFeature.tsx';
import { GlobalSearchResults } from '@/components/search/GlobalSearchResults.tsx';
import { rowLinkProps, toGlobalSearchRows } from '@/components/search/globalSearchRows.ts';
import { SemanticSearchField } from '@/components/search/SemanticSearchField.tsx';
import { useSemanticSearch } from '@/components/search/useSemanticSearch.ts';
import { CloseIcon, SearchIcon } from '@/theme/Icons.tsx';
import {
  Box,
  ClickAwayListener,
  Dialog,
  IconButton,
  Paper,
  Popper,
  type SxProps,
  type Theme,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { useNavigate } from '@tanstack/react-router';
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
 *
 * Below the `md` breakpoint the app bar has no room for a field, so a search
 * icon opens the same state in a full-screen dialog instead.
 */
export const GlobalSearch = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const isCompact = useMediaQuery(theme.breakpoints.down('md'));
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  // State, not a ref: `anchorEl` and the width below are read during render,
  // and the lint rule for refs forbids reading `.current` there.
  const [anchorEl, setAnchorEl] = useState<HTMLDivElement | null>(null);
  const [query, setQuery] = useState('');
  // Closing keeps the query: the user scans the list, opens one hit, and comes
  // back for the next without retyping.
  const [isDismissed, setIsDismissed] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  const handleSearch = useCallback((value: string) => {
    setQuery(value);
    setIsDismissed(false);
    setActiveIndex(-1);
  }, []);

  const { results, isFetching, isError, hasQuery } = useSemanticSearch({
    query,
    limit: RESULTS_PER_TYPE,
  });
  const rows = useMemo(() => toGlobalSearchRows(results), [results]);
  const isOpen = hasQuery && !isDismissed;

  const close = () => {
    setIsDismissed(true);
    setActiveIndex(-1);
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (!isOpen) return;

    // `(index + 1) % 0` is NaN, so the arrow branches need rows to exist.
    if (rows.length === 0 && event.key !== 'Escape') return;

    if (event.key === 'Escape') {
      // SearchBar clears the field on Escape. Stopping the event here makes the
      // first press close the dropdown and the second one clear the query.
      event.stopPropagation();
      close();
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveIndex((index) => (index + 1) % rows.length);
      return;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex((index) => (index <= 0 ? rows.length - 1 : index - 1));
      return;
    }
    if (event.key === 'Enter' && activeIndex >= 0) {
      // Stop SearchBar re-submitting the query the row is about to leave.
      event.preventDefault();
      event.stopPropagation();
      void navigate(rowLinkProps(rows[activeIndex]));
      close();
    }
  };

  const closeMobile = () => {
    setIsMobileOpen(false);
    close();
  };

  if (isCompact) {
    return (
      <EmbeddingFeature>
        <IconButton
          aria-label="Search"
          onClick={() => setIsMobileOpen(true)}
          sx={{ color: 'primary.contrastText' }}
        >
          <SearchIcon />
        </IconButton>
        <Dialog fullScreen open={isMobileOpen} onClose={closeMobile}>
          <Box
            onKeyDownCapture={handleKeyDown}
            sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 1 }}
          >
            <Box sx={{ flex: 1 }}>
              <SemanticSearchField
                value={query}
                onChange={handleSearch}
                placeholder={GLOBAL_SEARCH_PLACEHOLDER}
                autoFocus
              />
            </Box>
            {/* The only way to dismiss a dead-end search: Escape has no keyboard on
                a phone, and a query with no results leaves no row to tap instead. */}
            <IconButton edge="end" color="inherit" onClick={closeMobile} aria-label="Close dialog">
              <CloseIcon />
            </IconButton>
          </Box>
          {isOpen && (
            <GlobalSearchResults
              rows={rows}
              isFetching={isFetching}
              isError={isError}
              activeIndex={activeIndex}
              onSelect={closeMobile}
            />
          )}
        </Dialog>
      </EmbeddingFeature>
    );
  }

  return (
    <EmbeddingFeature>
      <ClickAwayListener onClickAway={close}>
        <Box
          ref={setAnchorEl}
          // Capture phase: `SearchBar`'s own Escape handler runs on bubble and
          // would clear the field before `stopPropagation` here could stop it.
          onKeyDownCapture={handleKeyDown}
          // Focus events bubble in React, so this reopens after a dismissal
          // without SearchBar having to expose an onFocus of its own.
          onFocus={() => setIsDismissed(false)}
          sx={{ flexGrow: 1, maxWidth: 480, mx: 'auto' }}
        >
          <SemanticSearchField
            value={query}
            onChange={handleSearch}
            placeholder={GLOBAL_SEARCH_PLACEHOLDER}
            sx={appBarFieldSx}
          />
          <Popper
            open={isOpen}
            anchorEl={anchorEl}
            placement="bottom-start"
            sx={{ zIndex: (theme) => theme.zIndex.appBar + 1, width: anchorEl?.clientWidth }}
          >
            <Paper elevation={8} sx={{ mt: 1, maxHeight: 480, overflowY: 'auto' }}>
              <GlobalSearchResults
                rows={rows}
                isFetching={isFetching}
                isError={isError}
                activeIndex={activeIndex}
                onSelect={close}
              />
            </Paper>
          </Popper>
        </Box>
      </ClickAwayListener>
    </EmbeddingFeature>
  );
};
