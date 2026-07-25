import { getGetRecentlyViewedBooksQueryKey, useGetBookDetails } from '@/api/generated/books/books';
import { FadeInOut } from '@/components/animations/FadeInOut.tsx';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { ScrollToTopButton } from '@/components/buttons/ScrollToTopButton.tsx';
import { PageContainer } from '@/components/layout/Layouts.tsx';
import { queryClient } from '@/lib/queryClient';
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

  const [leftSidebarEl, setLeftSidebarEl] = useState<HTMLDivElement | null>(null);
  const [fabContainerEl, setFabContainerEl] = useState<HTMLDivElement | null>(null);

  // Update recently viewed on mount
  useEffect(() => {
    void queryClient.invalidateQueries({
      queryKey: getGetRecentlyViewedBooksQueryKey(),
    });
  }, []);

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
        fabContainerEl,
      }}
    >
      <PageContainer maxWidth="xl">
        <Box
          sx={{
            position: 'fixed',
            bottom: { xs: 'calc(80px + env(safe-area-inset-bottom))', lg: 24 },
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
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: '280px 1fr',
                  gap: 4,
                  alignItems: 'start',
                  mt: 5,
                }}
              >
                <Box>
                  <DesktopNavLinks bookId={String(bookId)} />
                  <div ref={setLeftSidebarEl} />
                </Box>
                <Box>
                  <Outlet />
                </Box>
              </Box>
            </>
          ) : (
            <Box sx={{ maxWidth: '800px', mx: 'auto' }}>
              <BookTitle book={book} />
              <Outlet />
            </Box>
          )}
        </FadeInOut>
        {!isDesktop && <MobileBottomNav />}
      </PageContainer>
    </BookPageProvider>
  );
};
