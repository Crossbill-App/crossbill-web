import { SortIcon } from '@/theme/Icons.tsx';
import { IconButton, Tooltip } from '@mui/material';
import { useTranslation } from 'react-i18next';

interface SortToggleProps {
  isReversed: boolean;
  onToggle: () => void;
}

/** Newest/oldest ordering toggle, shown beside a book tab's search field. */
export const SortToggle = ({ isReversed, onToggle }: SortToggleProps) => {
  const { t } = useTranslation();

  return (
    <Tooltip
      title={
        isReversed
          ? t('book.common.sortToggle.oldestFirst')
          : t('book.common.sortToggle.newestFirst')
      }
    >
      <IconButton
        onClick={onToggle}
        sx={{
          mt: '1px',
          color: isReversed ? 'primary.main' : 'text.secondary',
          '&:hover': { color: 'primary.main' },
        }}
      >
        <SortIcon />
      </IconButton>
    </Tooltip>
  );
};
