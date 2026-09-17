import { ColorDot } from '@/components/highlights/ColorDot.tsx';
import { getContrastColor } from '@/utils/colorUtils.ts';
import { Box, Chip } from '@mui/material';

interface LabelChipProps {
  /** What the chip says. */
  name: string;
  /** The label's colour, a hex string; drawn as the dot and as the fill when selected. */
  color: string;
  /** Shown after the name in parentheses. */
  count: number;
  isSelected?: boolean;
  onClick: () => void;
}

/** A highlight label as a selectable chip: its colour as a dot, its name, and its count. */
export const LabelChip = ({ name, color, count, isSelected, onClick }: LabelChipProps) => (
  <Chip
    label={
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
        <ColorDot color={color} />
        <span>{`${name} (${count})`}</span>
      </Box>
    }
    variant={isSelected ? 'filled' : 'outlined'}
    onClick={onClick}
    // The one chip that keeps its own colour when selected: it is the
    // colour the highlight was made in on the device.
    sx={
      isSelected
        ? {
            backgroundColor: color,
            color: getContrastColor(color),
            '&:hover': {
              backgroundColor: color,
              opacity: 0.85,
              transform: 'translateY(-1px)',
            },
          }
        : undefined
    }
  />
);
