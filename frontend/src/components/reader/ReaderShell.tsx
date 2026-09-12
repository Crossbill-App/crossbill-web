import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip.tsx';
import { useBodyScrollLock } from '@/hooks/useBodyScrollLock.ts';
import { CloseIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { Box, Toolbar, Typography } from '@mui/material';

export interface ReaderShellProps {
  title: string;
  onClose: () => void;
}

/** The reader's full-viewport frame: a title bar, a way out, and the viewport. */
export const ReaderShell = ({ title, onClose }: ReaderShellProps) => {
  // A fixed overlay never scrolls the body, which is what arms pull-to-refresh.
  useBodyScrollLock(true);

  return (
    <Box
      sx={{
        position: 'fixed',
        inset: 0,
        zIndex: (t) => t.zIndex.appBar + 1,
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'background.default',
        color: 'text.primary',
      }}
    >
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Toolbar variant="dense" sx={{ gap: 1 }}>
          <Typography variant="h6" component="h1" noWrap sx={{ flex: 1, minWidth: 0 }}>
            {title}
          </Typography>
          <IconButtonWithTooltip
            label="Close reader"
            onClick={onClose}
            edge="end"
            icon={<CloseIcon sx={{ fontSize: ICON_SIZE.ui }} />}
          />
        </Toolbar>
      </Box>

      <Box sx={{ flex: 1, minHeight: 0, position: 'relative' }} />
    </Box>
  );
};
