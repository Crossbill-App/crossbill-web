import type { ChapterDigestResponse } from '@/api/generated/model';
import { DigestContent } from '@/pages/BookPage/Structure/DigestContent.tsx';
import { Typography } from '@mui/material';
import { CollapsibleSection } from './CollapsibleSection.tsx';

interface DigestSummarySectionProps {
  digestSummary?: ChapterDigestResponse;
  defaultExpanded: boolean;
}

export const DigestSummarySection = ({
  digestSummary,
  defaultExpanded,
}: DigestSummarySectionProps) => {
  return (
    <CollapsibleSection title="Chapter summary" defaultExpanded={defaultExpanded}>
      {digestSummary ? (
        <DigestContent content={digestSummary} />
      ) : (
        <Typography
          variant="body2"
          sx={{
            color: 'text.secondary',
          }}
        >
          No chapter summary available
        </Typography>
      )}
    </CollapsibleSection>
  );
};
