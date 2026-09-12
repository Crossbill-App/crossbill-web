import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip.tsx';
import { useReaderSession } from '@/components/reader/useReaderSession.ts';
import { useBodyScrollLock } from '@/hooks/useBodyScrollLock.ts';
import { CloseIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { Box, Button, Toolbar, Typography, type SxProps, type Theme } from '@mui/material';

export interface ReaderShellProps {
  bookId: number;
  title: string;
  onClose: () => void;
}

const overlaySx: SxProps<Theme> = {
  position: 'fixed',
  inset: 0,
  zIndex: (t) => t.zIndex.appBar + 1,
  display: 'flex',
  flexDirection: 'column',
  backgroundColor: 'background.default',
  color: 'text.primary',
};

interface ReaderMessageProps {
  children: string;
  onClose: () => void;
}

const ReaderMessage = ({ children, onClose }: ReaderMessageProps) => (
  <Box sx={overlaySx}>
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
      <Button variant="outlined" onClick={onClose}>
        Back to book
      </Button>
    </Box>
  </Box>
);

/** The reader's full-viewport frame: a title bar, a way out, and the viewport. */
export const ReaderShell = ({ bookId, title, onClose }: ReaderShellProps) => {
  // A fixed overlay never scrolls the body, which is what arms pull-to-refresh.
  useBodyScrollLock(true);
  const { status } = useReaderSession(bookId);

  if (status === 'error') {
    return (
      <ReaderMessage onClose={onClose}>
        The reader could not start a session for this book. Please try again later.
      </ReaderMessage>
    );
  }

  return (
    <Box sx={overlaySx}>
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
