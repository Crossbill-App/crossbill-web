import { Spinner } from '@/components/animations/Spinner.tsx';
import { Stack } from '@mui/material';

/** What stands in for the page while the book is on its way to the screen. */
export const ReaderLoading = () => (
  <Stack
    aria-label="Loading the book"
    aria-busy="true"
    sx={{ position: 'absolute', inset: 0, justifyContent: 'center' }}
  >
    <Spinner />
  </Stack>
);
