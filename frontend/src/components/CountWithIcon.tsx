import { ICON_SIZE } from '@/theme/iconSizes';
import { countLabel } from '@/utils/counts';
import type { SvgIconComponent } from '@mui/icons-material';
import { Box } from '@mui/material';

interface CountWithIconProps {
  icon: SvgIconComponent;
  count: number;
  /** Singular noun, for the label a screen reader reads instead of the glyph. */
  noun: string;
}

/**
 * A count as an icon and a number, or nothing at all when the count is zero.
 *
 * Inline so it sits inside a metadata line as happily as in a flex row, and it
 * inherits its font size from whatever wraps it.
 */
export const CountWithIcon = ({ icon: Icon, count, noun }: CountWithIconProps) =>
  count > 0 ? (
    <Box
      component="span"
      role="img"
      aria-label={countLabel(count, noun)}
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 0.5,
        verticalAlign: 'middle',
      }}
    >
      <Icon sx={{ fontSize: ICON_SIZE.inline }} />
      {count}
    </Box>
  ) : null;
