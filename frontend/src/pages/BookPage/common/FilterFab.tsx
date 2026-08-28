import { FilterListIcon } from '@/theme/Icons';
import { Badge, Zoom } from '@mui/material';
import Fab from '@mui/material/Fab';

interface FilterFabProps {
  /** How many filters are on; the badge says it outright, the colour echoes it. */
  activeFilterCount: number;
  onClick: () => void;
}

export const FilterFab = ({ activeFilterCount, onClick }: FilterFabProps) => {
  const isFiltered = activeFilterCount > 0;

  return (
    <Zoom in={true} mountOnEnter unmountOnExit>
      <Badge badgeContent={activeFilterCount} color="secondary" overlap="circular">
        <Fab
          size="small"
          color={isFiltered ? 'primary' : 'default'}
          aria-label={isFiltered ? `Open filters (${activeFilterCount} active)` : 'Open filters'}
          onClick={() => onClick()}
        >
          <FilterListIcon />
        </Fab>
      </Badge>
    </Zoom>
  );
};
