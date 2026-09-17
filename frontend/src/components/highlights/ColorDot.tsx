import { Box } from '@mui/material';

/** A label's or a palette colour's hue, as the small circle that stands for it. */
export const ColorDot = ({ color }: { color: string }) => (
  <Box
    sx={{
      width: 8,
      height: 8,
      borderRadius: '50%',
      backgroundColor: color,
      flexShrink: 0,
    }}
  />
);
