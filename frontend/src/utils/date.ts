import { DateTime } from 'luxon';

/**
 * The browser's own locale — the one source for every date the app renders,
 * including the date pickers.
 */
export const browserLocale = (): string => Intl.DateTimeFormat().resolvedOptions().locale;

/**
 * The browser's own IANA timezone. The server counts a reader's calendar days
 * in it, so a session at half past midnight belongs to the day the reader had
 * rather than the day UTC had.
 */
export const browserTimeZone = (): string => Intl.DateTimeFormat().resolvedOptions().timeZone;

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
 * A calendar day as a reader would name it: "Today" and "Yesterday" for the two
 * days they can place without reading a date, and the app's usual format for
 * every day before that.
 *
 * The two named days are decided against the browser's own clock, which is the
 * clock the server counted the reader's days on.
 */
export const formatDay = (date: string): string => {
  const days = Math.round(
    DateTime.fromISO(date).startOf('day').diff(DateTime.now().startOf('day'), 'days').days
  );

  if (days === 0) {
    return 'Today';
  }
  if (days === -1) {
    return 'Yesterday';
  }
  return formatDate(date);
};

/**
 * Format time from ISO string (e.g., "2:30 PM")
 */
export const formatTime = (date: string | Date): string => {
  return DateTime.fromISO(date.toString()).toLocaleString(DateTime.TIME_SIMPLE);
};

/**
 * The app's one way of saying how long something took: "1h 23m", or "45m" when
 * it ran under the hour.
 */
export const formatSeconds = (seconds: number): string => {
  // Rounded to whole minutes before the hours are split off. Rounding the
  // remainder instead lets it reach 60, which reads as "1h 60m".
  const totalMinutes = Math.round(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
};

/**
 * Calculate duration between two ISO timestamps
 * Returns formatted string like "1h 23m" or "45m"
 */
export const formatDuration = (startTime: string, endTime: string): string =>
  formatSeconds(DateTime.fromISO(endTime).diff(DateTime.fromISO(startTime)).as('seconds'));
