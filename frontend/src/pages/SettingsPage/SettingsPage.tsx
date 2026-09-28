import { useUpdateMe } from '@/api/generated/users/users';
import { FormErrorAlert } from '@/components/FormErrorAlert.tsx';
import { EmbeddingFeature } from '@/components/features/EmbeddingFeature.tsx';
import { RHFTextField } from '@/components/inputs/RHFTextField.tsx';
import { PageContainer } from '@/components/layout/Layouts.tsx';
import { PageTitle } from '@/components/typography/PageTitle.tsx';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { useAuth } from '@/context/AuthContext';
import { useSnackbar } from '@/context/SnackbarContext';
import { Box, Button, Typography } from '@mui/material';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { AboutSection } from './AboutSection.tsx';
import { EmbeddingBackfillSection } from './EmbeddingBackfillSection.tsx';

interface EmailFormValues {
  email: string;
}

const EmailForm = () => {
  const { t } = useTranslation();
  const { user, refreshUser } = useAuth();
  const { showSnackbar } = useSnackbar();

  const {
    control,
    handleSubmit,
    setError,
    formState: { errors, isDirty },
  } = useForm<EmailFormValues>({
    defaultValues: { email: user?.email ?? '' },
  });

  const updateMutation = useUpdateMe();

  const onSubmit = async ({ email }: EmailFormValues) => {
    try {
      await updateMutation.mutateAsync({ data: { email: email.trim() } });
      await refreshUser();
      showSnackbar(t('settings.emailForm.updated'), 'success');
    } catch {
      setError('root', { message: t('settings.emailForm.updateFailed') });
    }
  };

  return (
    <Box sx={{ mb: 6 }}>
      <SectionTitle showDivider>{t('settings.emailForm.title')}</SectionTitle>

      <FormErrorAlert message={errors.root?.message} />

      <Box component="form" onSubmit={handleSubmit(onSubmit)}>
        <RHFTextField
          name="email"
          control={control}
          rules={{
            required: t('settings.emailForm.emailEmpty'),
            validate: (value) => value.trim().length > 0 || t('settings.emailForm.emailEmpty'),
          }}
          label={t('common.fields.email')}
          fullWidth
          margin="normal"
          slotProps={{ htmlInput: { maxLength: 100 } }}
        />
        <Button
          type="submit"
          variant="contained"
          disabled={updateMutation.isPending || !isDirty}
          sx={{ mt: 2 }}
        >
          {updateMutation.isPending ? t('common.status.saving') : t('settings.emailForm.save')}
        </Button>
      </Box>
    </Box>
  );
};

interface PasswordFormValues {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

const EMPTY_PASSWORD_FORM: PasswordFormValues = {
  currentPassword: '',
  newPassword: '',
  confirmPassword: '',
};

const PasswordForm = () => {
  const { t } = useTranslation();
  const { logout } = useAuth();
  const { showSnackbar } = useSnackbar();

  const {
    control,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<PasswordFormValues>({
    defaultValues: EMPTY_PASSWORD_FORM,
  });

  const updateMutation = useUpdateMe();

  const onSubmit = async ({ currentPassword, newPassword }: PasswordFormValues) => {
    try {
      await updateMutation.mutateAsync({
        data: {
          current_password: currentPassword,
          new_password: newPassword,
        },
      });
      showSnackbar(t('settings.passwordForm.updated'), 'success');
      reset(EMPTY_PASSWORD_FORM);
      // The server revokes every session on a password change, this one
      // included. Sign out now rather than let the access token expire into a
      // confusing failure a few minutes from now.
      await logout();
    } catch {
      setError('root', {
        message: t('settings.passwordForm.updateFailed'),
      });
    }
  };

  return (
    <Box>
      <SectionTitle showDivider>{t('settings.passwordForm.title')}</SectionTitle>
      <Typography variant="body2" sx={{ mb: 3, color: 'text.secondary' }}>
        {t('settings.passwordForm.description')}
      </Typography>

      <FormErrorAlert message={errors.root?.message} />

      <Box component="form" onSubmit={handleSubmit(onSubmit)}>
        <RHFTextField
          name="currentPassword"
          control={control}
          rules={{ required: t('settings.passwordForm.currentPassword.required') }}
          label={t('settings.passwordForm.currentPassword.label')}
          type="password"
          fullWidth
          margin="normal"
          autoComplete="current-password"
        />
        <RHFTextField
          name="newPassword"
          control={control}
          rules={{
            required: t('settings.passwordForm.newPassword.required'),
            minLength: { value: 8, message: t('settings.passwordForm.newPassword.minLength') },
          }}
          label={t('settings.passwordForm.newPassword.label')}
          type="password"
          fullWidth
          margin="normal"
          autoComplete="new-password"
          helperText={t('settings.passwordForm.newPassword.helper')}
        />
        <RHFTextField
          name="confirmPassword"
          control={control}
          rules={{
            required: t('settings.passwordForm.confirmPassword.required'),
            validate: (value, values) =>
              value === values.newPassword || t('common.validation.passwordsDoNotMatch'),
          }}
          label={t('settings.passwordForm.confirmPassword.label')}
          type="password"
          fullWidth
          margin="normal"
          autoComplete="new-password"
        />
        <Button
          type="submit"
          variant="contained"
          disabled={updateMutation.isPending}
          sx={{ mt: 2 }}
        >
          {updateMutation.isPending ? t('common.status.saving') : t('settings.passwordForm.save')}
        </Button>
      </Box>
    </Box>
  );
};

export const SettingsPage = () => {
  const { t } = useTranslation();

  return (
    <PageContainer maxWidth="sm">
      <PageTitle text={t('common.nav.settings')} component="h1" />

      <EmailForm />
      <PasswordForm />

      <EmbeddingFeature>
        <EmbeddingBackfillSection />
      </EmbeddingFeature>

      <AboutSection />
    </PageContainer>
  );
};
