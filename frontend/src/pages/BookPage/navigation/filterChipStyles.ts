import type { SxProps, Theme } from '@mui/material';

const filterChipBaseSx = {
  cursor: 'pointer',
  transition: 'all 0.2s ease',
  py: 0.25,
  px: 0.5,
} satisfies SxProps<Theme>;

const filterChipOutlinedSx = {
  borderColor: 'divider',
  '&:hover': {
    bgcolor: 'action.hover',
    borderColor: 'secondary.light',
    transform: 'translateY(-1px)',
  },
} satisfies SxProps<Theme>;

const filterChipSelectedSx = {
  '&:hover': {
    bgcolor: 'primary.dark',
    transform: 'translateY(-1px)',
  },
} satisfies SxProps<Theme>;

/**
 * The geometry and motion of a chip that selects something — a tag, a label, a
 * note type, a reading stage. One padding, one transition, one hover lift, so
 * chips sitting in the same drawer cannot behave differently.
 *
 * A label chip overrides the *colour* on top of this, because a highlight
 * label's own colour is meaningful; nothing else should.
 */
export const filterChipSx = (isSelected: boolean): SxProps<Theme> => ({
  ...filterChipBaseSx,
  ...(isSelected ? filterChipSelectedSx : filterChipOutlinedSx),
});
