import { useDialogStackEntry } from '@/components/dialogs/dialogStack.ts';
import type { DialogNavigation } from '@/components/dialogs/useDialogHorizontalNavigation.ts';
import { lockBodyScroll, unlockBodyScroll } from '@/lib/bodyScrollLock.ts';
import { ArrowBackIcon, ArrowForwardIcon, CloseIcon } from '@/theme/Icons.tsx';
import {
  Box,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { useEffect, type ReactNode } from 'react';

interface CommonDialogProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  footerActions?: ReactNode;
  /**
   * Paging to the previous/next entity, rendered centred in the footer at
   * every width, and bound to the left/right arrow keys. Wider screens
   * additionally get the controls beside the content
   * (`CommonDialogHorizontalNavigation`); the footer is the pair that is
   * always in the same place, whatever the dialog is showing.
   */
  navigation?: DialogNavigation;
  maxWidth?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  isLoading?: boolean;
  headerElement?: ReactNode;
}

/**
 * Common dialog component with standard structure:
 * - Header with title and close button
 * - Scrollable content area
 * - Optional footer with action buttons and, on phones, entity paging
 * - Mobile-friendly with fullscreen mode on small screens
 * - Safe-area padding for devices with rounded corners (iPhone)
 */
export const CommonDialog = ({
  open,
  onClose,
  title,
  children,
  footerActions,
  navigation,
  maxWidth = 'sm',
  isLoading = false,
  headerElement,
}: CommonDialogProps) => {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));
  const isTopmostDialog = useDialogStackEntry(open);

  const footerNavigation = navigation ? (
    <Box sx={{ display: 'flex', gap: 1 }}>
      <IconButton
        onClick={navigation.onPrevious}
        disabled={!navigation.hasPrevious || isLoading}
        aria-label="Previous"
      >
        <ArrowBackIcon />
      </IconButton>
      <IconButton
        onClick={navigation.onNext}
        disabled={!navigation.hasNext || isLoading}
        aria-label="Next"
      >
        <ArrowForwardIcon />
      </IconButton>
    </Box>
  ) : null;

  // Lock body scroll when dialog is open
  useEffect(() => {
    if (!open) return;

    lockBodyScroll();
    return unlockBodyScroll;
  }, [open]);

  useEffect(() => {
    if (!open || !navigation) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // A dialog opened on top of this one shadows it, whether or not it pages
      // between entities of its own.
      if (!isTopmostDialog()) return;

      const target = e.target as HTMLElement;

      // Don't navigate when user is typing in an input field
      const isEditableElement =
        target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable;

      // Don't navigate when user is interacting with element inside area which is marked as to prevent
      // navigation by the special attribute
      const isInPreventNavigationArea = target.closest('[data-prevent-navigation="true"]');

      if (isEditableElement || isInPreventNavigationArea) return;

      if (e.key === 'ArrowLeft' && navigation.hasPrevious) {
        e.preventDefault();
        navigation.onPrevious();
      } else if (e.key === 'ArrowRight' && navigation.hasNext) {
        e.preventDefault();
        navigation.onNext();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, navigation, isTopmostDialog]);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth={maxWidth}
      fullWidth
      fullScreen={fullScreen}
      scroll="paper"
      disableScrollLock={true}
      slotProps={{
        backdrop: {
          sx: {
            // Prevent touch scrolling on backdrop
            touchAction: 'none',
            // Ensure backdrop covers entire viewport including Safari UI
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            // Use height that accounts for iOS Safari address bar
            height: '100dvh',
            minHeight: '-webkit-fill-available',
          },
        },
      }}
      sx={{
        // Prevent overscroll behavior on mobile
        '& .MuiDialog-container': {
          overscrollBehavior: 'contain',
          // Ensure container covers full viewport on iOS
          height: '100dvh',
          minHeight: '-webkit-fill-available',
        },
        // Ensure dialog paper prevents touch scrolling propagation
        '& .MuiDialog-paper': {
          overscrollBehavior: 'contain',
          // Prevent any layout shifts on iOS
          position: 'relative',
          // On fullscreen, ensure it fills the entire viewport
          ...(fullScreen && {
            height: '100dvh',
            minHeight: '-webkit-fill-available',
            maxHeight: '100dvh',
          }),
        },
        // Enable smooth scrolling within dialog content on iOS
        '& .MuiDialogContent-root': {
          // iOS-specific smooth scrolling
          WebkitOverflowScrolling: 'touch',
          // Prevent overscroll bounce from propagating to body
          overscrollBehavior: 'contain',
          // Ensure content can scroll
          touchAction: 'pan-y',
        },
        // Prevent touch events on header and footer from affecting body
        '& .MuiDialogTitle-root': {
          touchAction: 'none',
        },
        '& .MuiDialogActions-root': {
          touchAction: 'none',
        },
      }}
    >
      <DialogTitle>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          {title}
          <IconButton
            edge="end"
            color="inherit"
            onClick={onClose}
            aria-label="Close dialog"
            disabled={isLoading}
          >
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent dividers sx={{ pt: 0, px: 0 }}>
        {headerElement && (
          <Box
            sx={{
              width: '100%',
              px: 0,
              pt: 0,
              pb: 0,
              mb: 3,
            }}
          >
            {headerElement}
          </Box>
        )}
        <Box sx={{ px: 3 }}>{children}</Box>
      </DialogContent>

      {(footerActions || footerNavigation) && (
        <DialogActions
          sx={{
            justifyContent: 'space-between',
            // Add safe-area padding for iPhone rounded corners
            // Uses max() to ensure minimum 16px padding, but respects safe-area-inset-bottom
            pb: 'max(16px, calc(16px + env(safe-area-inset-bottom)))',
            pr: 2,
            pl: 2,
          }}
        >
          {footerNavigation ? (
            <>
              {/* Spacer opposite the actions, so the arrows sit on the bar's
                  centre rather than the centre of whatever is left over. */}
              <Box sx={{ flex: 1 }} />
              {footerNavigation}
              <Box sx={{ flex: 1, display: 'flex', justifyContent: 'flex-end' }}>
                {footerActions}
              </Box>
            </>
          ) : (
            footerActions
          )}
        </DialogActions>
      )}
    </Dialog>
  );
};
