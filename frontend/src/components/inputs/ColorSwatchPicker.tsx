import { SelectedIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { getContrastColor, type ColorOption } from '@/utils/colorUtils.ts';
import { Box, IconButton, Tooltip } from '@mui/material';

/** Diameter of a single swatch, in px. */
const SWATCH_SIZE = 28;

interface ColorSwatchPickerProps {
  /** The colors to choose from. */
  colors: readonly ColorOption[];
  /** Currently selected hex value, if any. Matched case-insensitively. */
  value?: string | null;
  /** Called with the hex value of the clicked swatch. */
  onChange: (color: string) => void;
  /** Accessible name for the group of swatches. */
  label: string;
}

/**
 * A single-selection palette of color swatches.
 *
 * Each swatch is a toggle button, so the selected color is announced without
 * relying on the check mark alone.
 */
export const ColorSwatchPicker = ({ colors, value, onChange, label }: ColorSwatchPickerProps) => {
  const selectedValue = value?.toLowerCase();

  return (
    <Box role="group" aria-label={label} sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
      {colors.map((color) => {
        const isSelected = color.value.toLowerCase() === selectedValue;

        return (
          <Tooltip key={color.value} title={color.name}>
            <IconButton
              aria-label={color.name}
              aria-pressed={isSelected}
              onClick={() => onChange(color.value)}
              sx={(theme) => ({
                width: SWATCH_SIZE,
                height: SWATCH_SIZE,
                padding: 0,
                backgroundColor: color.value,
                boxShadow: isSelected ? theme.shadows[2] : theme.shadows[0],
                transition: theme.transitions.create(['transform', 'box-shadow']),
                '&:hover': {
                  backgroundColor: color.value,
                  transform: 'scale(1.15)',
                },
              })}
            >
              {isSelected && (
                <SelectedIcon
                  sx={{ fontSize: ICON_SIZE.inline, color: getContrastColor(color.value) }}
                />
              )}
            </IconButton>
          </Tooltip>
        );
      })}
    </Box>
  );
};
