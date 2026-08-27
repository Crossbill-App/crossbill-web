import { describe, expect, it } from 'vitest';
import { readingStageMarker } from './readingStageMarker.ts';
import { READING_STAGE_LABELS } from './readingStages.ts';

describe('readingStageMarker', () => {
  it('marks skimming and reading as the same in-progress marker', () => {
    expect(readingStageMarker('skimming')?.Icon).toBe(readingStageMarker('reading')?.Icon);
    expect(readingStageMarker('reading')?.color).toBe('primary');
  });

  it('marks finished and reflected as the same done marker', () => {
    expect(readingStageMarker('finished')?.Icon).toBe(readingStageMarker('reflected')?.Icon);
    expect(readingStageMarker('reflected')?.color).toBe('primary');
  });

  it('renders no marker for to_read or an unset stage', () => {
    expect(readingStageMarker('to_read')).toBeNull();
    expect(readingStageMarker(null)).toBeNull();
    expect(readingStageMarker(undefined)).toBeNull();
  });

  it('renders no marker for a stage it does not know', () => {
    expect(readingStageMarker('shelved')).toBeNull();
  });

  it('labels a marker with the exact stage, not the bucket', () => {
    expect(readingStageMarker('skimming')?.label).toBe(READING_STAGE_LABELS.skimming);
    expect(readingStageMarker('reading')?.label).toBe(READING_STAGE_LABELS.reading);
    expect(readingStageMarker('finished')?.label).toBe(READING_STAGE_LABELS.finished);
    expect(readingStageMarker('reflected')?.label).toBe(READING_STAGE_LABELS.reflected);
  });
});
