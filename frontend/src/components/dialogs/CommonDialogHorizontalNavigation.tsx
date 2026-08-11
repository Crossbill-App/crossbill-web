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
 * Only from `sm` up, where there is room beside the content for them. Narrower
 * than that the same navigation lives in the dialog footer, which `CommonDialog`
 * renders — a phone has no spare horizontal room, and the footer is within
 * thumb reach in a way the content's edges are not.
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
