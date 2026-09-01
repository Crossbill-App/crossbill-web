import { PageContainer } from '@/components/layout/Layouts.tsx';
import { PageTitle } from '@/components/typography/PageTitle.tsx';
import { Box, Typography } from '@mui/material';
import { ReadingActivity } from './components/ReadingActivity';
import { RecentBooks } from './components/RecentBooks';
import { RecentCaptures } from './components/RecentCaptures';

/**
 * The reader's dashboard: what they were last reading, how the year has gone,
 * and what they last marked in a book. Browsing every book lives on the
 * library page, which the app bar reaches from here as from anywhere.
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

      <ReadingActivity />

      <RecentCaptures />
    </PageContainer>
  );
};
