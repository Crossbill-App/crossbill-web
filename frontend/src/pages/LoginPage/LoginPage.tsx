import { FeatureGate } from '@/components/features/FeatureGate.tsx';
import { RHFTextField } from '@/components/inputs/RHFTextField.tsx';
import { PageTitle } from '@/components/typography/PageTitle.tsx';
import { useAuth } from '@/context/AuthContext';
import { Alert, Box, Button, Container, Link, Paper, Typography } from '@mui/material';
import { Link as RouterLink, useNavigate } from '@tanstack/react-router';
import { useForm } from 'react-hook-form';

interface LoginFormValues {
  email: string;
  password: string;
}

export const LoginPage = () => {
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
      setError('root', { message: 'Invalid email or password' });
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
        <Paper
          elevation={3}
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
            <PageTitle text="Sign in to Crossbill" component="h1" />
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
              rules={{ required: 'Password is required' }}
              label="Password"
              type="password"
              fullWidth
              margin="normal"
              autoComplete="current-password"
            />
            <Button
              type="submit"
              variant="contained"
              fullWidth
              size="large"
              disabled={isSubmitting}
              sx={{ mt: 3 }}
            >
              {isSubmitting ? 'Signing in...' : 'Sign in'}
            </Button>
          </Box>

          <FeatureGate flag="user_registrations" value={true}>
            <Box sx={{ mt: 3, textAlign: 'center' }}>
              <Typography
                variant="body2"
                sx={{
                  color: 'text.secondary',
                }}
              >
                Don't have an account?{' '}
                <Link component={RouterLink} to="/register" underline="hover">
                  Create one
                </Link>
              </Typography>
            </Box>
          </FeatureGate>
        </Paper>
      </Box>
    </Container>
  );
};
