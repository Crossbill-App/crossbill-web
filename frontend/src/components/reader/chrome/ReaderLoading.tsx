import { Spinner } from '@/components/animations/Spinner.tsx';
import { Stack } from '@mui/material';
import { useTranslation } from 'react-i18next';

/** What stands in for the page while the book is on its way to the screen. */
export const ReaderLoading = () => {
  const { t } = useTranslation();

  return (
    <Stack
      aria-label={t('reader.readingSurface.loading')}
      aria-busy="true"
      sx={{ position: 'absolute', inset: 0, justifyContent: 'center' }}
    >
      <Spinner />
    </Stack>
  );
};
