import type { readerPageColors } from '@/components/reader/preferences/readerPreferences.ts';
import { alpha, Box, Typography } from '@mui/material';

export interface ReaderFooterProps {
  progression: number | undefined;
  colors: ReturnType<typeof readerPageColors>;
}

const BookProgress = ({
  colors,
  progression,
}: {
  progression: number | undefined;
  colors: ReturnType<typeof readerPageColors>;
}) => (
  <Typography variant="body2" noWrap sx={{ color: alpha(colors.text, 0.7) }}>
    {pageLabel(progression)}
  </Typography>
);

const pageLabel = (progression: number | undefined) =>
  progression === undefined ? '' : `${Math.round(progression * 100)}%`;

export const ReaderFooter = ({ progression, colors }: ReaderFooterProps) => (
  <Box
    component="footer"
    sx={{
      display: 'flex',
      alignItems: 'center',
      gap: 2,
      // Held open before the position is known, so the page is not laid out
      // twice when the label arrives.
      minHeight: 'calc(32px + env(safe-area-inset-bottom))',
      px: 2,
      // Clear of an iPhone's home indicator, which the page runs under.
      pb: 'env(safe-area-inset-bottom)',
      borderTop: 1,
      borderColor: alpha(colors.text, 0.12),
    }}
  >
    <Box sx={{display: 'flex', flex: 1, justifyContent: 'right'}}>
      {progression && (
        <BookProgress progression={progression} colors={colors} />
      )}
    </Box>
  </Box>
);
