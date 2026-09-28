import { Button, Dialog, DialogActions, DialogContent, DialogContentText } from '@mui/material';
import { useId, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

interface ConfirmationDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
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
  confirmText,
  cancelText,
  confirmColor = 'primary',
  isLoading = false,
}: ConfirmationDialogProps) => {
  const { t } = useTranslation();
  const messageId = useId();

  return (
    <Dialog
      open={open}
      onClose={isLoading ? undefined : onClose}
      maxWidth="xs"
      fullWidth
      role="alertdialog"
      aria-labelledby={messageId}
    >
      <DialogContent id={messageId}>
        {typeof message === 'string' ? <DialogContentText>{message}</DialogContentText> : message}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={isLoading}>
          {cancelText ?? t('common.actions.cancel')}
        </Button>
        <Button
          onClick={onConfirm}
          color={confirmColor}
          variant="contained"
          disabled={isLoading}
          autoFocus
        >
          {confirmText ?? t('common.actions.confirm')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
