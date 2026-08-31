import { Box, Pagination } from '@mui/material';

interface PaginationControlsProps {
  /** Total number of pages. One page or fewer renders nothing. */
  count: number;
  page: number;
  onChange: (page: number) => void;
}

/** The app's one pager: centred under a list, and hidden while it fits on one page. */
export const PaginationControls = ({ count, page, onChange }: PaginationControlsProps) => {
  if (count <= 1) {
    return null;
  }

  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
      <Pagination
        count={count}
        page={page}
        onChange={(_event, value) => onChange(value)}
        color="primary"
        size="large"
        showFirstButton
        showLastButton
      />
    </Box>
  );
};
