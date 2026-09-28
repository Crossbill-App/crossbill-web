import { RetryIcon } from '@/theme/Icons.tsx';
import { Alert, Box, Button, CircularProgress } from '@mui/material';
import { useTranslation } from 'react-i18next';

interface SessionErrorProps {
  error: string | null;
  hasSession: boolean;
  isCreating: boolean;
  onRetry: () => void;
}

export const SessionError = ({ error, hasSession, isCreating, onRetry }: SessionErrorProps) => {
  const { t } = useTranslation();

  if (isCreating) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error && !hasSession) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', mt: 4, gap: 2 }}>
        <Alert severity="error" sx={{ width: '100%', maxWidth: 400 }}>
          {error}
        </Alert>
        <Button variant="outlined" startIcon={<RetryIcon />} onClick={onRetry}>
          {t('common.actions.tryAgain')}
        </Button>
      </Box>
    );
  }

  if (error && hasSession) {
    return (
      <Alert severity="error" sx={{ alignSelf: 'flex-start', maxWidth: '80%' }}>
        {error}
      </Alert>
    );
  }

  return null;
};
