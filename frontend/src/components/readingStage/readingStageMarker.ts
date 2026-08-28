import { ReadingDoneIcon, ReadingInProgressIcon } from '@/theme/Icons.tsx';
import type { SvgIconComponent } from '@mui/icons-material';
import { READING_STAGE_LABELS, type ReadingStageValue } from './readingStages.ts';

export interface ReadingStageMarker {
  Icon: SvgIconComponent;
  label: string;
}

const IN_PROGRESS = { Icon: ReadingInProgressIcon } as const;
const DONE = { Icon: ReadingDoneIcon } as const;

/** Six stages collapse into three markers, and `to_read` deliberately gets none:
 *  unread is the default state of a library, so marking it would mark everything. */
const STAGE_MARKERS: Record<ReadingStageValue, Omit<ReadingStageMarker, 'label'> | null> = {
  to_read: null,
  skimming: IN_PROGRESS,
  reading: IN_PROGRESS,
  finished: DONE,
  reflected: DONE,
  did_not_finish: null,
};

/**
 * Resolve a reading stage to the marker the library grid renders for it.
 *
 * Takes a plain string so callers can pass the generated API type without a
 * cast, and returns null for anything it does not recognise — a stage added on
 * the backend first renders no marker rather than an undefined label.
 */
export const readingStageMarker = (stage: string | null | undefined): ReadingStageMarker | null => {
  if (!stage || !(stage in STAGE_MARKERS)) return null;
  const marker = STAGE_MARKERS[stage as ReadingStageValue];
  if (!marker) return null;
  return { ...marker, label: READING_STAGE_LABELS[stage as ReadingStageValue] };
};
