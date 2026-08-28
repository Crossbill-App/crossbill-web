import { useUpdateMe } from '@/api/generated/users/users';
import { EmbeddingFeature } from '@/components/features/EmbeddingFeature.tsx';
import { RHFTextField } from '@/components/inputs/RHFTextField.tsx';
import { PageContainer } from '@/components/layout/Layouts.tsx';
import { PageTitle } from '@/components/typography/PageTitle.tsx';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { useAuth } from '@/context/AuthContext';
import { Alert, Box, Button, Typography } from '@mui/material';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { AboutSection } from './AboutSection.tsx';
import { EmbeddingBackfillSection } from './EmbeddingBackfillSection.tsx';

interface EmailFormValues {
  email: string;
}

const EmailForm = () => {
  const { user, refreshUser } = useAuth();
  const [success, setSuccess] = useState(false);

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
    setSuccess(false);
    try {
      await updateMutation.mutateAsync({ data: { email: email.trim() } });
      await refreshUser();
      setSuccess(true);
    } catch {
      setError('root', { message: 'Failed to update email' });
    }
  };

  return (
    <Box sx={{ mb: 6 }}>
      <SectionTitle showDivider>Profile</SectionTitle>

      {success && (
        <Alert severity="success" sx={{ mb: 2 }}>
          Email updated successfully
        </Alert>
      )}

      {errors.root && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {errors.root.message}
        </Alert>
      )}

      <Box component="form" onSubmit={handleSubmit(onSubmit)}>
        <RHFTextField
          name="email"
          control={control}
          rules={{
            required: 'Email cannot be empty',
            validate: (value) => value.trim().length > 0 || 'Email cannot be empty',
          }}
          label="Email"
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
          {updateMutation.isPending ? 'Saving...' : 'Save email'}
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
  const [success, setSuccess] = useState(false);
  const { logout } = useAuth();

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
    setSuccess(false);
    try {
      await updateMutation.mutateAsync({
        data: {
          current_password: currentPassword,
          new_password: newPassword,
        },
      });
      setSuccess(true);
      reset(EMPTY_PASSWORD_FORM);
      // The server revokes every session on a password change, this one
      // included. Sign out now rather than let the access token expire into a
      // confusing failure a few minutes from now.
      await logout();
    } catch {
      setError('root', {
        message: 'Failed to update password. Check your current password.',
      });
    }
  };

  return (
    <Box>
      <SectionTitle showDivider>Change password</SectionTitle>
      <Typography variant="body2" sx={{ mb: 3, color: 'text.secondary' }}>
        Update your password to keep your account secure
      </Typography>

      {success && (
        <Alert severity="success" sx={{ mb: 2 }}>
          Password updated successfully
        </Alert>
      )}

      {errors.root && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {errors.root.message}
        </Alert>
      )}

      <Box component="form" onSubmit={handleSubmit(onSubmit)}>
        <RHFTextField
          name="currentPassword"
          control={control}
          rules={{ required: 'Current password is required' }}
          label="Current password"
          type="password"
          fullWidth
          margin="normal"
          autoComplete="current-password"
        />
        <RHFTextField
          name="newPassword"
          control={control}
          rules={{
            required: 'New password is required',
            minLength: { value: 8, message: 'New password must be at least 8 characters' },
          }}
          label="New password"
          type="password"
          fullWidth
          margin="normal"
          autoComplete="new-password"
          helperText="Minimum 8 characters"
        />
        <RHFTextField
          name="confirmPassword"
          control={control}
          rules={{
            required: 'Please confirm your new password',
            validate: (value, values) => value === values.newPassword || 'Passwords do not match',
          }}
          label="Confirm new password"
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
          {updateMutation.isPending ? 'Saving...' : 'Save password'}
        </Button>
      </Box>
    </Box>
  );
};

export const SettingsPage = () => {
  return (
    <PageContainer maxWidth="sm">
      <PageTitle text="Settings" component="h1" />

      <EmailForm />
      <PasswordForm />

      <EmbeddingFeature>
        <EmbeddingBackfillSection />
      </EmbeddingFeature>

      <AboutSection />
    </PageContainer>
  );
};
