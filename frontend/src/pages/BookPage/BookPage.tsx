import { useGetBookDetails } from '@/api/generated/books/books';
import { FadeInOut } from '@/components/animations/FadeInOut.tsx';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { ScrollToTopButton } from '@/components/buttons/ScrollToTopButton.tsx';
import {
  APP_BAR_HEIGHT,
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
import { useTabContentSnap } from '@/pages/BookPage/navigation/useTabContentSnap.ts';
import { Alert, Box, useMediaQuery, useTheme } from '@mui/material';
import { Outlet, useLocation, useParams } from '@tanstack/react-router';
import { useEffect, useState } from 'react';

/**
 * The air a snapped-to tab heading keeps between itself and the app bar above
 * it. Three spacing units: at less than that the heading reads as pinned to
 * the edge of the screen rather than as the top of the page.
 */
const SNAP_AIR = '24px';

export const BookPage = () => {
  const { bookId } = useParams({ strict: false });
  // Keys the tab fade below. Search params are excluded on purpose: filtering
  // or searching within a tab must not replay the animation.
  const pathname = useLocation({ select: (location) => location.pathname });
  const { data: book, isLoading, isError } = useGetBookDetails(Number(bookId));

  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up('lg'));
  const cache = useCacheEvents();
  const { isSnackbarOpen } = useSnackbar();

  const [leftSidebarEl, setLeftSidebarEl] = useState<HTMLDivElement | null>(null);
  const [rightSidebarEl, setRightSidebarEl] = useState<HTMLDivElement | null>(null);
  const [fabContainerEl, setFabContainerEl] = useState<HTMLDivElement | null>(null);

  const tabContentRef = useTabContentSnap({ enabled: !isDesktop, bookId, pathname });

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
                  <FadeInOut ekey={pathname} animateOnMount={false}>
                    <Outlet />
                  </FadeInOut>
                </Box>
                <Box ref={setRightSidebarEl} />
              </Box>
            </>
          ) : (
            <Box sx={{ maxWidth: '800px', mx: 'auto' }}>
              <BookTitle book={book} />
              {/* Tall enough to fill the viewport on its own, so switching to a
                  tab with little in it still has somewhere to snap to: without
                  the minimum, a short tab cannot scroll past the book header
                  and the reader is back to seeing the cover they tapped from.
                  The scroll margin keeps the tab's heading clear of the sticky
                  app bar it would otherwise land under, with air to spare. */}
              <Box
                component="main"
                ref={tabContentRef}
                sx={{
                  minHeight: {
                    xs: `calc(100dvh - ${APP_BAR_HEIGHT.xs} - ${BOTTOM_NAV_CLEARANCE})`,
                    sm: `calc(100dvh - ${APP_BAR_HEIGHT.sm} - ${BOTTOM_NAV_CLEARANCE})`,
                  },
                  scrollMarginTop: {
                    xs: `calc(${APP_BAR_HEIGHT.xs} + ${SNAP_AIR})`,
                    sm: `calc(${APP_BAR_HEIGHT.sm} + ${SNAP_AIR})`,
                  },
                }}
              >
                <FadeInOut ekey={pathname} animateOnMount={false}>
                  <Outlet />
                </FadeInOut>
              </Box>
            </Box>
          )}
        </FadeInOut>
        {!isDesktop && <MobileBottomNav />}
      </PageContainer>
    </BookPageProvider>
  );
};
