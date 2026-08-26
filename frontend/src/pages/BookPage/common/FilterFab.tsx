import { FilterListIcon } from '@/theme/Icons';
import { Zoom } from '@mui/material';
import Fab from '@mui/material/Fab';

export const FilterFab = ({
  filterEnabled,
  onClick,
}: {
  filterEnabled: boolean;
  onClick: () => void;
}) => {
  return (
    <Zoom in={true} mountOnEnter unmountOnExit>
      <Fab
        size="small"
        color={filterEnabled ? 'primary' : 'default'}
        aria-label={filterEnabled ? 'Open filters (filters active)' : 'Open filters'}
        onClick={() => onClick()}
      >
        <FilterListIcon />
      </Fab>
    </Zoom>
  );
};
