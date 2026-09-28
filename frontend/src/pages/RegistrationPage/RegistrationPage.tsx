import { AuthEmailField, AuthFormCard, AuthFormFooter } from '@/components/auth/AuthFormCard.tsx';
import { RHFTextField } from '@/components/inputs/RHFTextField.tsx';
import { useAuth } from '@/context/AuthContext';
import { getApiErrorMessage } from '@/utils/getApiErrorMessage.ts';
import { Link } from '@mui/material';
import { Link as RouterLink, useNavigate } from '@tanstack/react-router';
import { useForm } from 'react-hook-form';
import { Trans, useTranslation } from 'react-i18next';

const MIN_PASSWORD_LENGTH = 8;

interface RegistrationFormValues {
  email: string;
  password: string;
  confirmPassword: string;
}

export const RegistrationPage = () => {
  const { t } = useTranslation();
  const { register } = useAuth();
  const navigate = useNavigate();

  const {
    control,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegistrationFormValues>({
    defaultValues: { email: '', password: '', confirmPassword: '' },
  });

  const onSubmit = async ({ email, password }: RegistrationFormValues) => {
    try {
      await register(email, password);
      navigate({ to: '/' });
    } catch (err: unknown) {
      setError('root', {
        message: getApiErrorMessage(err, t('auth.registration.failed')),
      });
    }
  };

  return (
    <AuthFormCard
      title={t('auth.registration.title')}
      error={errors.root?.message}
      onSubmit={handleSubmit(onSubmit)}
      isSubmitting={isSubmitting}
      submitLabel={t('auth.registration.submit')}
      submittingLabel={t('auth.registration.submitting')}
      footer={
        <AuthFormFooter>
          <Trans
            i18nKey="auth.registration.haveAccount"
            components={{
              link: <Link component={RouterLink} to="/login" underline="hover" />,
            }}
          />
        </AuthFormFooter>
      }
    >
      <AuthEmailField control={control} />
      <RHFTextField
        name="password"
        control={control}
        rules={{
          required: t('common.validation.passwordRequired'),
          minLength: {
            value: MIN_PASSWORD_LENGTH,
            message: t('auth.registration.passwordMinLength', {
              minLength: MIN_PASSWORD_LENGTH,
            }),
          },
        }}
        label={t('common.fields.password')}
        type="password"
        fullWidth
        margin="normal"
        autoComplete="new-password"
        helperText={t('auth.registration.passwordHint', { minLength: MIN_PASSWORD_LENGTH })}
      />
      <RHFTextField
        name="confirmPassword"
        control={control}
        rules={{
          required: t('auth.registration.confirmPasswordRequired'),
          validate: (value, values) =>
            value === values.password || t('common.validation.passwordsDoNotMatch'),
        }}
        label={t('auth.registration.confirmPassword')}
        type="password"
        fullWidth
        margin="normal"
        autoComplete="new-password"
      />
    </AuthFormCard>
  );
};
