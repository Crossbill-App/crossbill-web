import type { ChapterPrereadingResponse } from '@/api/generated/model';
import { PrereadingContent } from '@/pages/BookPage/Structure/PrereadingContent.tsx';
import { Typography } from '@mui/material';
import { CollapsibleSection } from './CollapsibleSection.tsx';

interface PrereadingSummarySectionProps {
  prereadingSummary?: ChapterPrereadingResponse;
  defaultExpanded: boolean;
}

export const PrereadingSummarySection = ({
  prereadingSummary,
  defaultExpanded,
}: PrereadingSummarySectionProps) => {
  return (
    <CollapsibleSection title="Chapter summary" defaultExpanded={defaultExpanded}>
      {prereadingSummary ? (
        <PrereadingContent content={prereadingSummary} />
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
