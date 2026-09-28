import { FormErrorAlert } from '@/components/FormErrorAlert.tsx';
import { RHFTextField } from '@/components/inputs/RHFTextField.tsx';
import { PageTitle } from '@/components/typography/PageTitle.tsx';
import { Box, Button, Card, Container, Typography } from '@mui/material';
import type { FormEventHandler, ReactNode } from 'react';
import type { Control, FieldValues, Path } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

interface AuthFormCardProps {
  title: string;
  error?: string;
  onSubmit: FormEventHandler;
  isSubmitting: boolean;
  submitLabel: string;
  submittingLabel: string;
  /** The fields, between the error and the submit button. */
  children: ReactNode;
  /** The line under the card that links to the other auth page. */
  footer: ReactNode;
}

/** The centred card, logo, title and submit button the sign-in and sign-up pages share. */
export const AuthFormCard = ({
  title,
  error,
  onSubmit,
  isSubmitting,
  submitLabel,
  submittingLabel,
  children,
  footer,
}: AuthFormCardProps) => {
  const { t } = useTranslation();

  return (
    <Container maxWidth="sm">
      <Box
        sx={{
          minHeight: '80vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Card
          sx={{
            p: 4,
            width: '100%',
            maxWidth: 400,
          }}
        >
          <Box sx={{ textAlign: 'center', mb: 3 }}>
            <Box
              component="img"
              src="/icon-transparent.png"
              alt={t('common.appName')}
              sx={{ height: 64, width: 64, mb: 2 }}
            />
            <PageTitle text={title} component="h1" />
          </Box>

          <FormErrorAlert message={error} />

          <Box component="form" onSubmit={onSubmit}>
            {children}
            <Button
              type="submit"
              variant="contained"
              fullWidth
              size="large"
              disabled={isSubmitting}
              sx={{ mt: 3 }}
            >
              {isSubmitting ? submittingLabel : submitLabel}
            </Button>
          </Box>

          {footer}
        </Card>
      </Box>
    </Container>
  );
};

/** The footer line under an auth card. */
export const AuthFormFooter = ({ children }: { children: ReactNode }) => (
  <Box sx={{ mt: 3, textAlign: 'center' }}>
    <Typography variant="body2" sx={{ color: 'text.secondary' }}>
      {children}
    </Typography>
  </Box>
);

interface EmailFieldProps<T extends FieldValues> {
  control: Control<T>;
}

/** The email field both auth forms open with. */
export const AuthEmailField = <T extends FieldValues & { email: string }>({
  control,
}: EmailFieldProps<T>) => {
  const { t } = useTranslation();

  return (
    <RHFTextField
      name={'email' as Path<T>}
      control={control}
      rules={{ required: t('common.validation.emailRequired') }}
      label={t('common.fields.email')}
      fullWidth
      margin="normal"
      autoComplete="email"
      autoFocus
    />
  );
};
