import { PageContainer } from '@/components/layout/Layouts.tsx';
import { PageTitle } from '@/components/typography/PageTitle.tsx';
import { LibraryIcon } from '@/theme/Icons.tsx';
import { Box, Button, Typography } from '@mui/material';
import { Link } from '@tanstack/react-router';
import { RecentBooks } from './components/RecentBooks';

/**
 * The reader's dashboard: what they were last reading, and a way into the rest
 * of the library. Browsing every book lives on the library page — this one is
 * for what the reader is in the middle of.
 */
export const LandingPage = () => {
  return (
    <PageContainer maxWidth="xl">
      <Box sx={{ mt: { xs: 6, md: 8 }, mb: 6, textAlign: 'center' }}>
        <PageTitle text="Welcome to Crossbill" component="h1" />
        <Typography
          variant="body1"
          sx={{
            color: 'text.secondary',
            fontSize: '1.1rem',
          }}
        >
          Your reading companion
        </Typography>
      </Box>

      <RecentBooks />

      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 6 }}>
        <Button
          component={Link}
          to="/library"
          variant="outlined"
          size="large"
          startIcon={<LibraryIcon />}
        >
          Browse the library
        </Button>
      </Box>
    </PageContainer>
  );
};
