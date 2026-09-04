import { EmbeddingFeature } from '@/components/features/EmbeddingFeature.tsx';
import { GLOBAL_SEARCH_INSET_X } from '@/components/search/globalSearchLayout.ts';
import { GlobalSearchResults } from '@/components/search/GlobalSearchResults.tsx';
import {
  globalSearchRowDomId,
  rowLinkProps,
  toGlobalSearchRows,
} from '@/components/search/globalSearchRows.ts';
import { ContentSearchField } from '@/components/search/ContentSearchField.tsx';
import { useContentSearch } from '@/components/search/useContentSearch.ts';
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
import { useCallback, useId, useMemo, useState } from 'react';

const GLOBAL_SEARCH_PLACEHOLDER = 'Search...';

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

const RESULTS_PER_TYPE = 10;

/**
 * Global search over every book, in the app bar.
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
  const [anchorEl, setAnchorEl] = useState<HTMLDivElement | null>(null);
  const [query, setQuery] = useState('');
  // Closing keeps the query: the user scans the list, opens one hit, and comes
  // back for the next without retyping.
  const [isDismissed, setIsDismissed] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const listboxId = useId();

  // Adjusted during render, not an effect: the mobile dialog only exists
  // below `md`, so widening past it while open must not leave a phantom
  // dialog behind when the viewport narrows again. Tracking the previous
  // breakpoint is React's documented way to reset state on a prop change
  // without an extra render.
  const [prevIsCompact, setPrevIsCompact] = useState(isCompact);
  if (isCompact !== prevIsCompact) {
    setPrevIsCompact(isCompact);
    if (!isCompact) setIsMobileOpen(false);
  }

  const handleSearch = useCallback((value: string) => {
    setQuery(value);
    setIsDismissed(false);
    setActiveIndex(-1);
  }, []);

  const { results, isFetching, isError, hasQuery } = useContentSearch({
    query,
    limit: RESULTS_PER_TYPE,
  });
  const rows = useMemo(() => toGlobalSearchRows(results), [results]);
  const isOpen = hasQuery && !isDismissed;
  const activeRow = activeIndex >= 0 ? rows[activeIndex] : undefined;
  const comboboxHtmlInputProps = {
    role: 'combobox',
    'aria-expanded': isOpen,
    'aria-controls': listboxId,
    'aria-activedescendant': activeRow ? globalSearchRowDomId(activeRow) : undefined,
  } as const;

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
    // Bounds-checked rather than a `row === undefined` guard after indexing:
    // `noUncheckedIndexedAccess` is off project-wide, so the type checker
    // sees `rows[activeIndex]` as always defined and flags such a guard as
    // dead code. A background refetch can still shorten `rows` out from
    // under a previously set index, so the bound is checked for real here.
    if (event.key === 'Enter' && activeIndex >= 0 && activeIndex < rows.length) {
      const row = rows[activeIndex];
      // Stop SearchBar re-submitting the query the row is about to leave.
      event.preventDefault();
      event.stopPropagation();
      void navigate(rowLinkProps(row));
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
            // Reopens the dropdown when the field regains focus with a query
            // already in it, e.g. tapping the icon again after a prior visit.
            onFocus={() => setIsDismissed(false)}
            sx={{ px: GLOBAL_SEARCH_INSET_X, py: 2, display: 'flex', alignItems: 'center', gap: 1 }}
          >
            <Box sx={{ flex: 1 }}>
              <ContentSearchField
                value={query}
                onChange={handleSearch}
                placeholder={GLOBAL_SEARCH_PLACEHOLDER}
                autoFocus
                slotProps={{ htmlInput: comboboxHtmlInputProps }}
              />
            </Box>
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
              listboxId={listboxId}
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
          onKeyDownCapture={handleKeyDown}
          // Focus events bubble in React, so this reopens after a dismissal
          // without SearchBar having to expose an onFocus of its own.
          onFocus={() => setIsDismissed(false)}
          // A blur that lands outside both this box and the listbox (Tab to
          // the next control, or a click elsewhere) is a genuine dismissal —
          // never a reopen, which is what `SearchBar`'s own onBlur→onSearch
          // would otherwise cause. The listbox itself needs a separate check:
          // it renders through a `Popper`, portaled to `document.body`, so a
          // row is never a DOM descendant of this box even though clicking
          // one focuses it before the click fires — closing on that blur
          // would unmount the row out from under its own click.
          onBlur={(event) => {
            const nextFocus = event.relatedTarget;
            const staysInWidget =
              event.currentTarget.contains(nextFocus) ||
              document.getElementById(listboxId)?.contains(nextFocus);
            if (!staysInWidget) close();
          }}
          sx={{
            flexGrow: 1,
            width: {
              md: 680,
              lg: 800,
            },
            maxWidth: {
              md: 680,
              lg: 800,
            },
            mx: 'auto',
          }}
        >
          <ContentSearchField
            value={query}
            onChange={handleSearch}
            placeholder={GLOBAL_SEARCH_PLACEHOLDER}
            sx={appBarFieldSx}
            slotProps={{ htmlInput: comboboxHtmlInputProps }}
          />
          <Popper
            open={isOpen}
            anchorEl={anchorEl}
            placement="bottom-start"
            sx={{ zIndex: (theme) => theme.zIndex.appBar + 1, width: anchorEl?.clientWidth }}
          >
            <Paper elevation={8} sx={{ mt: 1, maxHeight: 680, overflowY: 'auto' }}>
              <GlobalSearchResults
                rows={rows}
                isFetching={isFetching}
                isError={isError}
                activeIndex={activeIndex}
                onSelect={close}
                listboxId={listboxId}
              />
            </Paper>
          </Popper>
        </Box>
      </ClickAwayListener>
    </EmbeddingFeature>
  );
};
