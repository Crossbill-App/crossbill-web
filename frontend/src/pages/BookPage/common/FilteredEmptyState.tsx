import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { Box, Button } from '@mui/material';

interface FilteredEmptyStateProps {
  /** What the list holds, plural and lower case: "highlights", "notes". */
  noun: string;
  onClearFilters: () => void;
}

/**
 * What a book tab says when its search and filters exclude everything, and the
 * control that undoes them. Without it the only way back is to find and unset
 * each chip, across a sidebar and a drawer.
 */
export const FilteredEmptyState = ({ noun, onClearFilters }: FilteredEmptyStateProps) => (
  <Box sx={{ py: 4, textAlign: 'center' }}>
    <EmptyStateText>No {noun} match the current filters.</EmptyStateText>
    <Button size="small" onClick={onClearFilters} sx={{ mt: 1 }}>
      Clear filters
    </Button>
  </Box>
);
