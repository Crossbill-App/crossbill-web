import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { Box, Button } from '@mui/material';
import { useTranslation } from 'react-i18next';

interface FilteredEmptyStateProps {
  /** The whole sentence, naming what the list holds: "No highlights match...". */
  message: string;
  onClearFilters: () => void;
}

/**
 * What a book tab says when its search and filters exclude everything, and the
 * control that undoes them. Without it the only way back is to find and unset
 * each chip, across a sidebar and a drawer.
 */
export const FilteredEmptyState = ({ message, onClearFilters }: FilteredEmptyStateProps) => {
  const { t } = useTranslation();

  return (
    <Box sx={{ py: 4, textAlign: 'center' }}>
      <EmptyStateText>{message}</EmptyStateText>
      <Button size="small" onClick={onClearFilters} sx={{ mt: 1 }}>
        {t('book.common.filteredEmptyState.clearFilters')}
      </Button>
    </Box>
  );
};
