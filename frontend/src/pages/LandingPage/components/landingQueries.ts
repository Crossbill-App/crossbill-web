import { useGetRecentBooks } from '@/api/generated/books/books';
import { useGetRecentCaptures } from '@/api/generated/captures/captures';
import { useGetLibraryReadingActivity } from '@/api/generated/statistics/statistics';
import { browserTimeZone } from '@/utils/date.ts';

export const RECENT_BOOKS_LIMIT = 8;

const CAPTURES_LIMIT = 8;

export const useRecentBooks = () => useGetRecentBooks({ limit: RECENT_BOOKS_LIMIT });

export const useReadingActivity = () => useGetLibraryReadingActivity({ tz: browserTimeZone() });

export const useRecentCaptures = () =>
  useGetRecentCaptures({ limit: CAPTURES_LIMIT, tz: browserTimeZone() });
