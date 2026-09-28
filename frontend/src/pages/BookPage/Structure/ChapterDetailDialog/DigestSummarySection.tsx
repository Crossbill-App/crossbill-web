import type { ChapterDigestResponse } from '@/api/generated/model';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { DigestContent } from '@/pages/BookPage/Structure/DigestContent.tsx';
import { Box, Typography } from '@mui/material';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

interface DigestSummarySectionProps {
  digestSummary?: ChapterDigestResponse;
  /** Sits on the summary's closing line, since its actions act on this chapter. */
  toolbar: ReactNode;
}

export const DigestSummarySection = ({ digestSummary, toolbar }: DigestSummarySectionProps) => {
  const { t } = useTranslation();

  return (
    <Box sx={{ py: 1.5 }}>
      <SectionTitle component="h3">{t('structure.chapterDetail.summary.title')}</SectionTitle>
      {digestSummary && <DigestContent content={digestSummary} />}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 2,
          mt: digestSummary ? 2 : 0,
          mb: 3,
        }}
      >
        {digestSummary ? (
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            {t('structure.digestContent.generatedOn', {
              date: new Date(digestSummary.generated_at).toLocaleDateString(),
            })}
          </Typography>
        ) : (
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            {t('structure.chapterDetail.summary.empty')}
          </Typography>
        )}
        {toolbar}
      </Box>
    </Box>
  );
};
