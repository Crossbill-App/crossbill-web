import { useGetBooks } from '@/api/generated/books/books';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { BookList } from '@/components/books/BookList.tsx';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { SearchBar } from '@/components/inputs/SearchBar.tsx';
import { PageContainer } from '@/components/layout/Layouts.tsx';
import { PaginationControls } from '@/components/PaginationControls.tsx';
import { PageTitle } from '@/components/typography/PageTitle.tsx';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { Alert, Box, Typography } from '@mui/material';
import { useNavigate, useSearch } from '@tanstack/react-router';
import { RecentBooks } from './components/RecentBooks';

const BOOKS_PER_PAGE = 32;

export const LandingPage = () => {
  const navigate = useNavigate({ from: '/' });
  const { search, page } = useSearch({ from: '/' });
  const searchText = search || '';
  const currentPage = page || 1;

  // Calculate offset for pagination
  const offset = (currentPage - 1) * BOOKS_PER_PAGE;

  const { data, isLoading, isError } = useGetBooks({
    search: searchText || undefined,
    offset,
    limit: BOOKS_PER_PAGE,
  });

  const handleSearch = (value: string) => {
    navigate({
      search: (prev) => ({
        ...prev,
        search: value || undefined,
        page: 1, // Reset to first page when searching
      }),
      replace: true,
    });
  };

  const handlePageChange = (value: number) => {
    navigate({
      search: (prev) => ({
        ...prev,
        page: value,
      }),
      replace: true,
    });
  };

  // Calculate total pages
  const totalPages = data?.total ? Math.ceil(data.total / BOOKS_PER_PAGE) : 0;

  return (
    <PageContainer maxWidth="xl">
      <Box sx={{ mt: { xs: 6, md: 8 }, mb: 6, textAlign: 'center' }}>
        <PageTitle text="Welcome to Crossbill" component="h1" />
        <Typography
          variant="body1"
          sx={{
            color: 'text.secondary',
            fontSize: '1.1rem',
          }}
        >
          Your reading companion
        </Typography>
      </Box>

      {/* Only show the recent row when not searching */}
      {!searchText && <RecentBooks />}

      <SectionTitle showDivider>All books</SectionTitle>

      <Box sx={{ mb: 3 }}>
        <SearchBar
          onSearch={handleSearch}
          placeholder="Search books by title or author..."
          initialValue={searchText}
        />
      </Box>

      {isLoading && <Spinner />}

      {isError && (
        <Box sx={{ py: 3 }}>
          <Alert severity="error">Failed to load books. Please try again later.</Alert>
        </Box>
      )}

      {data?.items && data.items.length === 0 && (
        <EmptyStateText variant="page">
          {searchText
            ? 'No books match your search.'
            : 'No books yet. Upload highlights from your e-reader to get started.'}
        </EmptyStateText>
      )}

      {data?.items && data.items.length > 0 && (
        <>
          <BookList books={data.items} pageKey={`${currentPage}-${searchText}`} />
          <PaginationControls count={totalPages} page={currentPage} onChange={handlePageChange} />
        </>
      )}
    </PageContainer>
  );
};
