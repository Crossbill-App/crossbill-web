import type { readerPageColors } from '@/components/reader/preferences/readerPreferences.ts';
import { alpha, Button, Stack, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';

export interface ExtensionBarProps {
  colors: ReturnType<typeof readerPageColors>;
  onCancel: () => void;
}

/** What to do while the far end of a passage is awaited, in the page's own colours. */
export const ExtensionBar = ({ colors, onCancel }: ExtensionBarProps) => {
  const { t } = useTranslation();

  return (
    <Stack
      role="group"
      aria-label={t('reader.extensionBar.label')}
      direction="row"
      spacing={1}
      sx={{
        alignItems: 'center',
        px: 1.5,
        py: 0.5,
        borderRadius: 1,
        border: 1,
        borderColor: alpha(colors.text, 0.12),
        boxShadow: (t) => t.shadows[2],
        backgroundColor: colors.background,
        color: colors.text,
      }}
    >
      <Typography variant="body2">{t('reader.extensionBar.hint')}</Typography>
      <Button size="small" color="inherit" onClick={onCancel}>
        {t('common.actions.cancel')}
      </Button>
    </Stack>
  );
};
