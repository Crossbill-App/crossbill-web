import { DateTime } from 'luxon';

/**
 * The browser's own locale — the one source for every date the app renders,
 * including the date pickers.
 */
export const browserLocale = (): string => Intl.DateTimeFormat().resolvedOptions().locale;

/**
 * The app's one rendered date format: `DATE_MED` in the browser's locale, so a
 * session header and the highlights beneath it never disagree.
 */
const formatDateTime = (dateTime: DateTime): string =>
  dateTime.setLocale(browserLocale()).toLocaleString(DateTime.DATE_MED);

/**
 * Format an ISO date string to a readable format
 */
export const formatDate = (date: string | Date): string =>
  formatDateTime(DateTime.fromISO(date.toString()));

/**
 * Format time from ISO string (e.g., "2:30 PM")
 */
export const formatTime = (date: string | Date): string => {
  return DateTime.fromISO(date.toString()).toLocaleString(DateTime.TIME_SIMPLE);
};

/**
 * Calculate duration between two ISO timestamps
 * Returns formatted string like "1h 23m" or "45m"
 */
export const formatDuration = (startTime: string, endTime: string): string => {
  const start = DateTime.fromISO(startTime);
  const end = DateTime.fromISO(endTime);
  const diff = end.diff(start, ['hours', 'minutes']);
  const hours = Math.floor(diff.hours);
  const minutes = Math.round(diff.minutes);

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
};
