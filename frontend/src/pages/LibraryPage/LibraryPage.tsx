import { useGetBooks } from '@/api/generated/books/books';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { BookList } from '@/components/books/BookList.tsx';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { SearchBar } from '@/components/inputs/SearchBar.tsx';
import { PageContainer } from '@/components/layout/Layouts.tsx';
import { PageHeader } from '@/components/layout/PageHeader.tsx';
import { PaginationControls } from '@/components/PaginationControls.tsx';
import { Alert, Box } from '@mui/material';
import { useNavigate, useSearch } from '@tanstack/react-router';

const BOOKS_PER_PAGE = 32;

/**
 * Every book the reader owns, searchable and paginated.
 *
 * The query lives in the URL rather than in state: a search worth running is
 * worth linking to, and the browser's back button is then the way out of one.
 */
export const LibraryPage = () => {
  const navigate = useNavigate({ from: '/library' });
  const { search, page } = useSearch({ from: '/library' });
  const searchText = search || '';
  const currentPage = page || 1;

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
        // A narrowed result set rarely runs as deep as the page the reader was
        // on, and page 7 of two pages is an empty screen.
        page: 1,
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

  const totalPages = data?.total ? Math.ceil(data.total / BOOKS_PER_PAGE) : 0;

  return (
    <PageContainer maxWidth="xl">
      <PageHeader
        title="Library"
        search={
          <SearchBar
            onSearch={handleSearch}
            placeholder="Search books by title or author..."
            initialValue={searchText}
          />
        }
        count={data ? { value: data.total, noun: 'book' } : undefined}
      />

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
