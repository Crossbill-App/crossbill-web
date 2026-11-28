import { FadeInOut } from '@/components/animations/FadeInOut.tsx';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { PageContainer } from '@/components/layout/Layouts.tsx';
import { PageTitle } from '@/components/typography/PageTitle.tsx';
import { Box, Typography } from '@mui/material';
import { motion } from 'motion/react';
import { useTranslation } from 'react-i18next';
import {
  useReadingActivity,
  useRecentBooks,
  useRecentCaptures,
} from './components/landingQueries.ts';
import { ReadingActivity } from './components/ReadingActivity';
import { RecentBooks } from './components/RecentBooks';
import { RecentCaptures } from './components/RecentCaptures';
import { PrototypeSwitcher } from '@/components/prototype/PrototypeSwitcher.tsx';
import { useSearch } from '@tanstack/react-router';
import {
  CapturesWithSideColumn,
  DUE_VARIANTS,
  EmbeddedReview,
  HeroStrip,
  PerBookSection,
} from './prototype/DueCardsPrototype.tsx';

/**
 * The reader's dashboard: what they were last reading, how the year has gone,
 * and what they last marked in a book. Browsing every book lives on the
 * library page, which the app bar reaches from here as from anywhere.
 *
 * Nothing renders until every section has its data, so the page fades in
 * once, whole, instead of each section popping in after its own request.
 * The spinner waits out a fast load, so it only shows when the wait is felt.
 */
export const LandingPage = () => {
  const { t } = useTranslation();
  // PROTOTYPE — throwaway variant switch for the due-cards element.
  const variant = useSearch({ from: '/' }).variant ?? 'A';
  const loading = [useRecentBooks(), useReadingActivity(), useRecentCaptures()].some(
    (query) => query.isLoading
  );

  return (
    <PageContainer maxWidth="xl">
      {loading ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3, duration: 0.2 }}
        >
          <Spinner />
        </motion.div>
      ) : (
        <FadeInOut ekey="landing">
          <Box sx={{ mt: { xs: 6, md: 8 }, mb: 6, textAlign: 'center' }}>
            <PageTitle text={t('landing.page.title')} component="h1" />
            <Typography
              variant="body1"
              sx={{
                color: 'text.secondary',
                fontSize: '1.1rem',
              }}
            >
              {t('landing.page.subtitle')}
            </Typography>
          </Box>

          {variant === 'A' && <HeroStrip />}

          <RecentBooks />

          <ReadingActivity />

          {variant === 'B' && <PerBookSection />}
          {variant === 'D' && <EmbeddedReview />}
          {variant === 'C' ? <CapturesWithSideColumn /> : <RecentCaptures />}
        </FadeInOut>
      )}
      <PrototypeSwitcher variants={DUE_VARIANTS} current={variant} />
    </PageContainer>
  );
};
