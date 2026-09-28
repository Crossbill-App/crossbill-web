import { AuthEmailField, AuthFormCard, AuthFormFooter } from '@/components/auth/AuthFormCard.tsx';
import { FeatureGate } from '@/components/features/FeatureGate.tsx';
import { RHFTextField } from '@/components/inputs/RHFTextField.tsx';
import { useAuth } from '@/context/AuthContext';
import { Link } from '@mui/material';
import { Link as RouterLink, useNavigate } from '@tanstack/react-router';
import { useForm } from 'react-hook-form';
import { Trans, useTranslation } from 'react-i18next';

interface LoginFormValues {
  email: string;
  password: string;
}

export const LoginPage = () => {
  const { t } = useTranslation();
  const { login } = useAuth();
  const navigate = useNavigate();

  const {
    control,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    defaultValues: { email: '', password: '' },
  });

  const onSubmit = async ({ email, password }: LoginFormValues) => {
    try {
      await login(email, password);
      navigate({ to: '/' });
    } catch {
      setError('root', { message: t('auth.login.invalidCredentials') });
    }
  };

  return (
    <AuthFormCard
      title={t('auth.login.title')}
      error={errors.root?.message}
      onSubmit={handleSubmit(onSubmit)}
      isSubmitting={isSubmitting}
      submitLabel={t('auth.shared.signIn')}
      submittingLabel={t('auth.login.submitting')}
      footer={
        <FeatureGate flag="user_registrations" value={true}>
          <AuthFormFooter>
            <Trans
              i18nKey="auth.login.noAccount"
              components={{
                link: <Link component={RouterLink} to="/register" underline="hover" />,
              }}
            />
          </AuthFormFooter>
        </FeatureGate>
      }
    >
      <AuthEmailField control={control} />
      <RHFTextField
        name="password"
        control={control}
        rules={{ required: t('common.validation.passwordRequired') }}
        label={t('common.fields.password')}
        type="password"
        fullWidth
        margin="normal"
        autoComplete="current-password"
      />
    </AuthFormCard>
  );
};
