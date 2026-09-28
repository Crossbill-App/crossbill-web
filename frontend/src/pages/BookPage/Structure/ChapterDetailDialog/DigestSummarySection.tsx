import type { ChapterDigestResponse } from '@/api/generated/model';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { DigestContent } from '@/pages/BookPage/Structure/DigestContent.tsx';
import { Box, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';

interface DigestSummarySectionProps {
  digestSummary?: ChapterDigestResponse;
}

export const DigestSummarySection = ({ digestSummary }: DigestSummarySectionProps) => {
  const { t } = useTranslation();

  return (
    <Box sx={{ py: 1.5 }}>
      <SectionTitle component="h3">{t('structure.chapterDetail.summary.title')}</SectionTitle>
      {digestSummary ? (
        <DigestContent content={digestSummary} />
      ) : (
        <Typography
          variant="body2"
          sx={{
            color: 'text.secondary',
          }}
        >
          {t('structure.chapterDetail.summary.empty')}
        </Typography>
      )}
    </Box>
  );
};
