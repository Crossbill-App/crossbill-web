import { i18n } from '@/i18n';

export const READING_STAGE_PROGRESSION = [
  'to_read',
  'skimming',
  'reading',
  'finished',
  'reflected',
] as const;

export type ReadingStageValue = (typeof READING_STAGE_PROGRESSION)[number] | 'did_not_finish';

// Getters, so each read resolves the copy in the current language rather than
// freezing whatever it was when this module loaded.
export const READING_STAGE_LABELS: Readonly<Record<ReadingStageValue, string>> = {
  get to_read() {
    return i18n.t('components.readingStage.labels.toRead');
  },
  get skimming() {
    return i18n.t('components.readingStage.labels.skimming');
  },
  get reading() {
    return i18n.t('components.readingStage.labels.reading');
  },
  get finished() {
    return i18n.t('components.readingStage.labels.finished');
  },
  get reflected() {
    return i18n.t('components.readingStage.labels.reflected');
  },
  get did_not_finish() {
    return i18n.t('components.readingStage.labels.didNotFinish');
  },
};

export const READING_STAGE_HINTS: Readonly<Partial<Record<ReadingStageValue, string>>> = {
  get skimming() {
    return i18n.t('components.readingStage.hints.skimming');
  },
  get finished() {
    return i18n.t('components.readingStage.hints.finished');
  },
  get reflected() {
    return i18n.t('components.readingStage.hints.reflected');
  },
};
