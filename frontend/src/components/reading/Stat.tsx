import { Box, Typography } from '@mui/material';

export interface StatProps {
  value: string;
  label: string;
}

/**
 * One number and what it counts. A paragraph rather than a heading: these are
 * facts about the reading, not sections of their own.
 */
export const Stat = ({ value, label }: StatProps) => (
  <Box>
    <Typography variant="h3" component="p">
      {value}
    </Typography>
    <Typography variant="body2" sx={{ color: 'text.secondary' }}>
      {label}
    </Typography>
  </Box>
);
