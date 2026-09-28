import { i18n } from '@/i18n';

/** The things the app counts, each with its plural forms under `common.counts`. */
export type CountUnit =
  'books' | 'pages' | 'highlights' | 'notes' | 'flashcards' | 'bookmarks' | 'sessions' | 'days';

/**
 * A count and its unit: "1 bookmark", "2 bookmarks". Wherever a number is shown
 * with the thing it counts — the stats strip, the chapter rows, the chapter
 * sidebar — it goes through here rather than each site reinventing the plural.
 */
export const countLabel = (count: number, unit: CountUnit) =>
  i18n.t(`common.counts.${unit}`, { count });
