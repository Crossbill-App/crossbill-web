import { useGetBookDetails } from '@/api/generated/books/books';
import { FadeInOut } from '@/components/animations/FadeInOut.tsx';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { ScrollToTopButton } from '@/components/buttons/ScrollToTopButton.tsx';
import {
  BOTTOM_NAV_CLEARANCE,
  PageContainer,
  SNACKBAR_CLEARANCE,
} from '@/components/layout/Layouts.tsx';
import { useSnackbar } from '@/context/SnackbarContext.tsx';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { BookPageProvider } from '@/pages/BookPage/BookPageContext.tsx';
import { BookTitle } from '@/pages/BookPage/BookTitle/BookTitle.tsx';
import { DesktopNavLinks } from '@/pages/BookPage/navigation/DesktopNavLinks.tsx';
import { MobileBottomNav } from '@/pages/BookPage/navigation/MobileBottomNav.tsx';
import { Alert, Box, useMediaQuery, useTheme } from '@mui/material';
import { Outlet, useParams } from '@tanstack/react-router';
import { useEffect, useState } from 'react';

export const BookPage = () => {
  const { bookId } = useParams({ strict: false });
  const { data: book, isLoading, isError } = useGetBookDetails(Number(bookId));

  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up('lg'));
  const cache = useCacheEvents();
  const { isSnackbarOpen } = useSnackbar();

  const [leftSidebarEl, setLeftSidebarEl] = useState<HTMLDivElement | null>(null);
  const [rightSidebarEl, setRightSidebarEl] = useState<HTMLDivElement | null>(null);
  const [fabContainerEl, setFabContainerEl] = useState<HTMLDivElement | null>(null);

  // Update recently viewed on mount. `cache` is memoised on the query client, so
  // listing it as a dependency does not make this run more than once.
  useEffect(() => {
    cache.bookViewed();
  }, [cache]);

  if (isLoading) {
    return (
      <PageContainer maxWidth="xl">
        <Spinner />
      </PageContainer>
    );
  }

  if (isError || !book) {
    return (
      <PageContainer maxWidth="xl">
        <Box sx={{ pt: 4 }}>
          <Alert severity="error">Failed to load book details. Please try again later.</Alert>
        </Box>
      </PageContainer>
    );
  }

  return (
    <BookPageProvider
      value={{
        book,
        isDesktop,
        leftSidebarEl,
        rightSidebarEl,
        fabContainerEl,
      }}
    >
      <PageContainer maxWidth="xl">
        <Box
          sx={{
            position: 'fixed',
            // Below `lg` the snackbar shares this corner and spans the
            // width, so the column rides above an open one. On `lg` the
            // snackbar is centred and narrow, and never reaches this far right.
            bottom: {
              xs: isSnackbarOpen
                ? `calc(${BOTTOM_NAV_CLEARANCE} + ${SNACKBAR_CLEARANCE})`
                : BOTTOM_NAV_CLEARANCE,
              lg: 24,
            },
            transition: theme.transitions.create('bottom'),
            right: 24,
            zIndex: 1000,
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
            alignItems: 'center',
          }}
        >
          <ScrollToTopButton />
          <div ref={setFabContainerEl} style={{ display: 'contents' }} />
        </Box>

        <FadeInOut ekey={`book-${bookId}`}>
          {isDesktop ? (
            <>
              <BookTitle book={book} />
              {/* One grid for every tab: fixed nav, a fixed content measure,
                  and a right rail whose column is reserved whether or not the
                  tab fills it. Tabs used to own their own layout, so the
                  content column was one of three widths depending on which one
                  you were looking at, and the page reflowed as you moved
                  between them. */}
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: '280px 1fr 280px',
                  gap: 4,
                  alignItems: 'start',
                  mt: 5,
                }}
              >
                <Box>
                  <DesktopNavLinks bookId={String(bookId)} />
                  <div ref={setLeftSidebarEl} />
                </Box>
                <Box component="main" sx={{ minWidth: 0 }}>
                  <Outlet />
                </Box>
                <Box ref={setRightSidebarEl} />
              </Box>
            </>
          ) : (
            <Box sx={{ maxWidth: '800px', mx: 'auto' }}>
              <BookTitle book={book} />
              <Box component="main">
                <Outlet />
              </Box>
            </Box>
          )}
        </FadeInOut>
        {!isDesktop && <MobileBottomNav />}
      </PageContainer>
    </BookPageProvider>
  );
};
