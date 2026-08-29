/* eslint-disable react-refresh/only-export-components */
import { BOTTOM_NAV_CLEARANCE_VAR } from '@/components/layout/Layouts.tsx';
import { Portal } from '@mui/material';
import Alert, { AlertColor } from '@mui/material/Alert';
import Snackbar from '@mui/material/Snackbar';
import { createContext, ReactNode, useCallback, useContext, useState } from 'react';

interface SnackbarContextType {
  showSnackbar: (message: string, severity?: AlertColor) => void;
  isSnackbarOpen: boolean;
}

const SnackbarContext = createContext<SnackbarContextType | undefined>(undefined);

interface SnackbarState {
  open: boolean;
  message: string;
  severity: AlertColor;
}

export function SnackbarProvider({ children }: { children: ReactNode }) {
  const [snackbar, setSnackbar] = useState<SnackbarState>({
    open: false,
    message: '',
    severity: 'info',
  });

  const showSnackbar = useCallback((message: string, severity: AlertColor = 'info') => {
    setSnackbar({ open: true, message, severity });
  }, []);

  const handleClose = useCallback((_event?: React.SyntheticEvent | Event, reason?: string) => {
    if (reason === 'clickaway') {
      return;
    }
    setSnackbar((prev) => ({ ...prev, open: false }));
  }, []);

  return (
    <SnackbarContext.Provider value={{ showSnackbar, isSnackbarOpen: snackbar.open }}>
      {children}
      {/* Portalled to the body so an open dialog does not bury the message
          under its `aria-hidden`, which would hide errors from assistive tech. */}
      <Portal>
        <Snackbar
          open={snackbar.open}
          autoHideDuration={6000}
          onClose={handleClose}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
          sx={{ marginBottom: `var(${BOTTOM_NAV_CLEARANCE_VAR}, 0px)` }}
        >
          <Alert
            onClose={handleClose}
            severity={snackbar.severity}
            variant="filled"
            sx={{ width: '100%' }}
          >
            {snackbar.message}
          </Alert>
        </Snackbar>
      </Portal>
    </SnackbarContext.Provider>
  );
}

export function useSnackbar() {
  const context = useContext(SnackbarContext);
  if (context === undefined) {
    throw new Error('useSnackbar must be used within a SnackbarProvider');
  }
  return context;
}
