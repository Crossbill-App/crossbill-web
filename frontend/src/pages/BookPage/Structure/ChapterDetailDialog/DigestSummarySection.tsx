import type { ChapterDigestResponse } from '@/api/generated/model';
import { DigestContent } from '@/pages/BookPage/Structure/DigestContent.tsx';
import { Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { CollapsibleSection } from './CollapsibleSection.tsx';

interface DigestSummarySectionProps {
  digestSummary?: ChapterDigestResponse;
  defaultExpanded: boolean;
}

export const DigestSummarySection = ({
  digestSummary,
  defaultExpanded,
}: DigestSummarySectionProps) => {
  const { t } = useTranslation();

  return (
    <CollapsibleSection
      title={t('structure.chapterDetail.summary.title')}
      defaultExpanded={defaultExpanded}
    >
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
    </CollapsibleSection>
  );
};
