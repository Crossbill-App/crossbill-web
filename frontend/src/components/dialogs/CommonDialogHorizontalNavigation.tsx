import type { DialogNavigation } from '@/components/dialogs/useDialogHorizontalNavigation.ts';
import { ArrowBackIcon, ArrowForwardIcon } from '@/theme/Icons.tsx';
import { Box, IconButton } from '@mui/material';
import type { ReactNode } from 'react';

interface CommonDialogHorizontalNavigationProps {
  navigation?: DialogNavigation;
  disabled?: boolean;
  children: ReactNode;
}

/**
 * Previous/next controls flanking a modal's content.
 *
 * Only from `sm` up, where there is room beside the content for them; a phone
 * has none to spare. They duplicate the footer's arrows, which `CommonDialog`
 * renders at every width — the same action within reach of where the eye
 * already is, rather than only at the bottom of the dialog.
 *
 * An arrow at the end of the list stays in place and turns invisible rather
 * than unmounting, so the content column does not shift sideways as the reader
 * pages into the first or last entity.
 */
export const CommonDialogHorizontalNavigation = ({
  navigation,
  disabled,
  children,
}: CommonDialogHorizontalNavigationProps) => (
  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
    {navigation && (
      <IconButton
        onClick={navigation.onPrevious}
        disabled={!navigation.hasPrevious || disabled}
        sx={{
          flexShrink: 0,
          display: { xs: 'none', sm: 'inline-flex' },
          visibility: navigation.hasPrevious ? 'visible' : 'hidden',
        }}
        aria-label="Previous"
      >
        <ArrowBackIcon />
      </IconButton>
    )}

    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 3,
        flex: 1,
        minWidth: 0,
      }}
    >
      {children}
    </Box>

    {navigation && (
      <IconButton
        onClick={navigation.onNext}
        disabled={!navigation.hasNext || disabled}
        sx={{
          flexShrink: 0,
          display: { xs: 'none', sm: 'inline-flex' },
          visibility: navigation.hasNext ? 'visible' : 'hidden',
        }}
        aria-label="Next"
      >
        <ArrowForwardIcon />
      </IconButton>
    )}
  </Box>
);
