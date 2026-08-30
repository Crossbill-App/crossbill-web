import { SortIcon } from '@/theme/Icons.tsx';
import { IconButton, Tooltip } from '@mui/material';

interface SortToggleProps {
  isReversed: boolean;
  onToggle: () => void;
}

/** Newest/oldest ordering toggle, shown beside a book tab's search field. */
export const SortToggle = ({ isReversed, onToggle }: SortToggleProps) => (
  <Tooltip title={isReversed ? 'Show oldest first' : 'Show newest first'}>
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
