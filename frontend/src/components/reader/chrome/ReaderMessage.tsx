import { overlaySx } from '@/components/reader/chrome/readerOverlay.ts';
import { Box, Button, Stack, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';

export interface ReaderMessageProps {
  children: string;
  onClose: () => void;
  /** Offered only where trying again could plausibly work. */
  onRetry?: () => void;
}

/** What stands in for the book when it cannot be opened: a way back, and sometimes a retry. */
export const ReaderMessage = ({ children, onClose, onRetry }: ReaderMessageProps) => {
  const { t } = useTranslation();

  return (
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
        <Typography role="alert">{children}</Typography>
        <Stack direction="row" spacing={2}>
          <Button variant="outlined" onClick={onClose}>
            {t('reader.message.backToBook')}
          </Button>
          {onRetry && (
            <Button variant="contained" onClick={onRetry}>
              {t('common.actions.tryAgain')}
            </Button>
          )}
        </Stack>
      </Box>
    </Box>
  );
};
