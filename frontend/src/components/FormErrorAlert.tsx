import { Alert } from '@mui/material';

/** A form's submit-level error, above its fields. Renders nothing without one. */
export const FormErrorAlert = ({ message }: { message?: string }) =>
  message ? (
    <Alert severity="error" sx={{ mb: 2 }}>
      {message}
    </Alert>
  ) : null;
