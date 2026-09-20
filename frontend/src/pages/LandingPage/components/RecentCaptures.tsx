import type { RecentCapture } from '@/api/generated/model';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { Eyebrow } from '@/components/typography/Eyebrow.tsx';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { formatDay } from '@/utils/date.ts';
import { Alert, Box } from '@mui/material';
import { useMemo } from 'react';

import { CaptureEntry } from './CaptureEntry.tsx';
import { useRecentCaptures } from './landingQueries.ts';

/** The feed's captures under the day each belongs to, newest day first. */
const byDay = (captures: RecentCapture[]): [string, RecentCapture[]][] => {
  const days = new Map<string, RecentCapture[]>();

  for (const capture of captures) {
    days.set(capture.day, [...(days.get(capture.day) ?? []), capture]);
  }

  return [...days];
};

/**
 * The dashboard's row of what the reader last marked: highlights on the
 * e-reader's own clock, notes on the reader's, cut into days.
 *
 * A reader who has captured nothing keeps the section and is told what will
 * fill it, the way the activity grid keeps its squares with nothing on them.
 */
export const RecentCaptures = () => {
  const { data, isError } = useRecentCaptures();
  const captures = data?.items;
  const days = useMemo(() => byDay(captures ?? []), [captures]);

  const empty = !isError && days.length === 0;

  return (
    <Box sx={{ mb: 6 }}>
      <SectionTitle showDivider>Recent highlights and notes</SectionTitle>

      {isError && (
        <Box sx={{ py: 3 }}>
          <Alert severity="error">Failed to load recent highlights and notes.</Alert>
        </Box>
      )}

      {empty && (
        <EmptyStateText>
          No highlights or notes yet. They appear here once you sync your e-reader.
        </EmptyStateText>
      )}

      {days.map(([day, dayCaptures]) => (
        <Box key={day} sx={{ mb: 1 }}>
          <Eyebrow component="h3" sx={{ px: 1.5, mt: 2, mb: 0.5 }}>
            {formatDay(day)}
          </Eyebrow>

          {dayCaptures.map((capture) => (
            <CaptureEntry key={`${capture.kind}-${capture.id}`} capture={capture} />
          ))}
        </Box>
      ))}
    </Box>
  );
};
