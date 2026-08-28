import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
} from '@mui/material';
import type { ReactNode } from 'react';

interface ConfirmationDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
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
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  confirmColor = 'primary',
  isLoading = false,
}: ConfirmationDialogProps) => (
  /* Never full-screen: a two-button question is the canonical small centred
     dialog at every width, and this one usually opens on top of an
     already-full-screen dialog whose context the reader still needs. */
  <Dialog open={open} onClose={isLoading ? undefined : onClose} maxWidth="xs" fullWidth>
    <DialogTitle>{title}</DialogTitle>
    <DialogContent>
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
