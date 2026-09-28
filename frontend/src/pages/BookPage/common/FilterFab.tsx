import { FilterListIcon } from '@/theme/Icons';
import { Badge, Zoom } from '@mui/material';
import Fab from '@mui/material/Fab';
import { useTranslation } from 'react-i18next';

interface FilterFabProps {
  /** How many filters are on; the badge says it outright, the colour echoes it. */
  activeFilterCount: number;
  onClick: () => void;
}

export const FilterFab = ({ activeFilterCount, onClick }: FilterFabProps) => {
  const { t } = useTranslation();
  const isFiltered = activeFilterCount > 0;

  return (
    <Zoom in={true} mountOnEnter unmountOnExit>
      <Badge
        badgeContent={activeFilterCount}
        color="secondary"
        overlap="circular"
        slotProps={{ badge: { sx: { zIndex: (theme) => theme.zIndex.fab + 1 } } }}
      >
        <Fab
          size="small"
          color={isFiltered ? 'primary' : 'default'}
          aria-label={
            isFiltered
              ? t('book.common.filterFab.openFiltersActive', { activeCount: activeFilterCount })
              : t('book.common.filterFab.openFilters')
          }
          onClick={() => onClick()}
        >
          <FilterListIcon />
        </Fab>
      </Badge>
    </Zoom>
  );
};
