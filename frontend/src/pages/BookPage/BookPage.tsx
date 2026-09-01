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
import { SidebarLayout } from '@/components/layout/SidebarLayout.tsx';
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

/** Air between a snapped-to tab heading and the app bar above it. */
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
              {/* One layout for every tab, so the content column keeps its
                  measure and the page does not reflow as you move between
                  them. The right rail's column is reserved whether or not the
                  tab fills it. */}
              <Box sx={{ mt: 5 }}>
                <SidebarLayout
                  left={
                    <>
                      <DesktopNavLinks bookId={String(bookId)} />
                      <div ref={setLeftSidebarEl} />
                    </>
                  }
                  right={<div ref={setRightSidebarEl} />}
                >
                  <FadeInOut ekey={pathname} animateOnMount={false}>
                    <Outlet />
                  </FadeInOut>
                </SidebarLayout>
              </Box>
            </>
          ) : (
            <Box sx={{ maxWidth: '800px', mx: 'auto' }}>
              <BookTitle book={book} />
              {/* Tall enough to fill the viewport, so a tab with little in it
                  still has somewhere to snap to. */}
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
