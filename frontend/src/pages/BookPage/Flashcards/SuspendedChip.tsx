import { SuspendIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { Chip } from '@mui/material';
import { useTranslation } from 'react-i18next';

export const SuspendedChip = () => {
  const { t } = useTranslation();

  return (
    <Chip
      variant="outlined"
      icon={<SuspendIcon />}
      label={t('flashcards.card.suspended')}
      sx={{
        color: 'text.secondary',
        borderColor: 'divider',
        '& .MuiChip-icon': { color: 'text.secondary', fontSize: ICON_SIZE.inline },
      }}
    />
  );
};
