import { useGetRecentCaptures } from '@/api/generated/captures/captures';
import type { RecentCapture } from '@/api/generated/model';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { browserTimeZone, formatDay } from '@/utils/date.ts';
import { Alert, Box, Typography } from '@mui/material';
import { useMemo } from 'react';

import { CaptureEntry } from './CaptureEntry.tsx';

const CAPTURES_LIMIT = 8;

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
 * Not drawn at all for a reader who has captured nothing, the way the activity
 * grid is not drawn for a reader with no year to show.
 */
export const RecentCaptures = () => {
  const { data, isLoading, isError } = useGetRecentCaptures({
    limit: CAPTURES_LIMIT,
    tz: browserTimeZone(),
  });
  const captures = data?.items;
  const days = useMemo(() => byDay(captures ?? []), [captures]);

  if (!isLoading && !isError && days.length === 0) {
    return null;
  }

  return (
    <Box sx={{ mb: 6 }}>
      <SectionTitle showDivider>Recent highlights and notes</SectionTitle>

      {isLoading && <Spinner />}

      {isError && (
        <Box sx={{ py: 3 }}>
          <Alert severity="error">Failed to load recent highlights and notes.</Alert>
        </Box>
      )}

      {days.map(([day, dayCaptures]) => (
        <Box key={day} sx={{ mb: 1 }}>
          <Typography
            variant="caption"
            component="h3"
            sx={{
              display: 'block',
              color: 'text.secondary',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              px: 1.5,
              mt: 2,
              mb: 0.5,
            }}
          >
            {formatDay(day)}
          </Typography>

          {dayCaptures.map((capture) => (
            <CaptureEntry key={`${capture.kind}-${capture.id}`} capture={capture} />
          ))}
        </Box>
      ))}
    </Box>
  );
};
