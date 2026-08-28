import { RHFTextField } from '@/components/inputs/RHFTextField.tsx';
import { PageTitle } from '@/components/typography/PageTitle.tsx';
import { useAuth } from '@/context/AuthContext';
import { getApiErrorMessage } from '@/utils/getApiErrorMessage.ts';
import { Alert, Box, Button, Card, Container, Link, Typography } from '@mui/material';
import { Link as RouterLink, useNavigate } from '@tanstack/react-router';
import { useForm } from 'react-hook-form';

interface RegistrationFormValues {
  email: string;
  password: string;
  confirmPassword: string;
}

export const RegistrationPage = () => {
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
        message: getApiErrorMessage(err, 'Registration failed. Please try again.'),
      });
    }
  };

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
              alt="Crossbill"
              sx={{ height: 64, width: 64, mb: 2 }}
            />
            <PageTitle text="Create your account" component="h1" />
          </Box>

          {errors.root && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {errors.root.message}
            </Alert>
          )}

          <Box component="form" onSubmit={handleSubmit(onSubmit)}>
            <RHFTextField
              name="email"
              control={control}
              rules={{ required: 'Email is required' }}
              label="Email"
              fullWidth
              margin="normal"
              autoComplete="email"
              autoFocus
            />
            <RHFTextField
              name="password"
              control={control}
              rules={{
                required: 'Password is required',
                minLength: {
                  value: 8,
                  message: 'Password must be at least 8 characters long',
                },
              }}
              label="Password"
              type="password"
              fullWidth
              margin="normal"
              autoComplete="new-password"
              helperText="Must be at least 8 characters"
            />
            <RHFTextField
              name="confirmPassword"
              control={control}
              rules={{
                required: 'Please confirm your password',
                validate: (value, values) => value === values.password || 'Passwords do not match',
              }}
              label="Confirm Password"
              type="password"
              fullWidth
              margin="normal"
              autoComplete="new-password"
            />
            <Button
              type="submit"
              variant="contained"
              fullWidth
              size="large"
              disabled={isSubmitting}
              sx={{ mt: 3 }}
            >
              {isSubmitting ? 'Creating account...' : 'Create account'}
            </Button>
          </Box>

          <Box sx={{ mt: 3, textAlign: 'center' }}>
            <Typography
              variant="body2"
              sx={{
                color: 'text.secondary',
              }}
            >
              Already have an account?{' '}
              <Link component={RouterLink} to="/login" underline="hover">
                Sign in
              </Link>
            </Typography>
          </Box>
        </Card>
      </Box>
    </Container>
  );
};
