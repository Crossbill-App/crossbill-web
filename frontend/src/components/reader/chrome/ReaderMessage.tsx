import { overlaySx } from '@/components/reader/chrome/readerOverlay.ts';
import { Box, Button, Stack, Typography } from '@mui/material';

export interface ReaderMessageProps {
  children: string;
  onClose: () => void;
  /** Offered only where trying again could plausibly work. */
  onRetry?: () => void;
}

/** What stands in for the book when it cannot be opened: a way back, and sometimes a retry. */
export const ReaderMessage = ({ children, onClose, onRetry }: ReaderMessageProps) => (
  <Box sx={{ ...overlaySx, backgroundColor: 'background.default', color: 'text.primary' }}>
    <Box
      sx={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2,
        p: 3,
        textAlign: 'center',
      }}
    >
      <Typography>{children}</Typography>
      <Stack direction="row" spacing={2}>
        <Button variant="outlined" onClick={onClose}>
          Back to book
        </Button>
        {onRetry && (
          <Button variant="contained" onClick={onRetry}>
            Try again
          </Button>
        )}
      </Stack>
    </Box>
  </Box>
);
