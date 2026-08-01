import { ArrowBackIcon, ArrowForwardIcon } from '@/theme/Icons.tsx';
import { Box, Button, IconButton } from '@mui/material';
import type { ReactNode } from 'react';
import type { SwipeableHandlers } from 'react-swipeable';

interface CommonDialogHorizontalNavigationProps {
  hasNavigation: boolean | undefined | ((newIndex: number) => void);
  hasPrevious: boolean | undefined | ((newIndex: number) => void);
  hasNext: boolean | undefined | ((newIndex: number) => void);
  onPrevious: () => void;
  onNext: () => void;
  swipeHandlers?: SwipeableHandlers;
  disabled?: boolean;
  children: ReactNode;
}

export const CommonDialogHorizontalNavigation = ({
  hasNavigation,
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
  swipeHandlers,
  disabled,
  children,
}: CommonDialogHorizontalNavigationProps) => (
  <>
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
      {hasNavigation && (
        <IconButton
          onClick={onPrevious}
          disabled={!hasPrevious || disabled}
          sx={{
            flexShrink: 0,
            display: { xs: 'none', sm: 'inline-flex' },
            visibility: hasPrevious ? 'visible' : 'hidden',
          }}
          aria-label="Previous"
        >
          <ArrowBackIcon />
        </IconButton>
      )}

      <Box
        {...swipeHandlers}
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

      {hasNavigation && (
        <IconButton
          onClick={onNext}
          disabled={!hasNext || disabled}
          sx={{
            flexShrink: 0,
            display: { xs: 'none', sm: 'inline-flex' },
            visibility: hasNext ? 'visible' : 'hidden',
          }}
          aria-label="Next"
        >
          <ArrowForwardIcon />
        </IconButton>
      )}
    </Box>

    {hasNavigation && (
      <Box
        sx={{
          display: { xs: 'flex', sm: 'none' },
          justifyContent: 'center',
          gap: 2,
          mt: 3,
          pt: 1,
        }}
      >
        <Button
          onClick={onPrevious}
          disabled={!hasPrevious || disabled}
          startIcon={<ArrowBackIcon />}
          variant="outlined"
          sx={{ flex: 1, maxWidth: '200px' }}
        >
          Previous
        </Button>
        <Button
          onClick={onNext}
          disabled={!hasNext || disabled}
          endIcon={<ArrowForwardIcon />}
          variant="outlined"
          sx={{ flex: 1, maxWidth: '200px' }}
        >
          Next
        </Button>
      </Box>
    )}
  </>
);
