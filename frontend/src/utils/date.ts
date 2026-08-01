import { DateTime } from 'luxon';

/**
 * Format a date string to a readable format
 */
export const formatDate = (date: string | Date): string => {
  return DateTime.fromISO(date.toString()).toLocaleString(DateTime.DATE_MED);
};

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
