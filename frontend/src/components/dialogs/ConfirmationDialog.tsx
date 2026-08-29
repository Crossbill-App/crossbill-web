import { Button, Dialog, DialogActions, DialogContent, DialogContentText } from '@mui/material';
import { useId, type ReactNode } from 'react';

interface ConfirmationDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  /**
   * The decision itself, as the question the two buttons answer — "Delete this
   * flashcard?" — carrying a second sentence only where something non-obvious
   * follows from a yes. It is the dialog's accessible name; there is no title,
   * because a one-sentence question does not need one summarised above it.
   */
  message: ReactNode;
  confirmText?: string;
  cancelText?: string;
  confirmColor?: 'primary' | 'error';
  isLoading?: boolean;
}

export const ConfirmationDialog = ({
  open,
  onClose,
  onConfirm,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  confirmColor = 'primary',
  isLoading = false,
}: ConfirmationDialogProps) => {
  const messageId = useId();

  return (
    /* Never full-screen: a two-button question is the canonical small centred
       dialog at every width, and this one usually opens on top of an
       already-full-screen dialog whose context the reader still needs. */
    <Dialog
      open={open}
      onClose={isLoading ? undefined : onClose}
      maxWidth="xs"
      fullWidth
      // A question that interrupts, not a panel the reader chose to open — so
      // assistive technology announces it the way it announces an alert.
      role="alertdialog"
      aria-labelledby={messageId}
    >
      <DialogContent id={messageId}>
        {typeof message === 'string' ? <DialogContentText>{message}</DialogContentText> : message}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={isLoading}>
          {cancelText}
        </Button>
        <Button
          onClick={onConfirm}
          color={confirmColor}
          variant="contained"
          disabled={isLoading}
          autoFocus
        >
          {confirmText}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
