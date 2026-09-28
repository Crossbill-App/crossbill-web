import type { HighlightLabelInBook } from '@/api/generated/model';
import { i18n } from '@/i18n';

/** What the book calls a highlighter before the reader names it: `yellow / lighten`. */
export const labelStyleName = (label: HighlightLabelInBook): string => {
  const parts = [label.device_color, label.device_style].filter(Boolean);
  return parts.length > 0 ? parts.join(' / ') : i18n.t('book.navigation.labels.unlabelled');
};
