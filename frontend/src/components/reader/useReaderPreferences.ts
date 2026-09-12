import {
  loadReaderPreferences,
  saveReaderPreferences,
} from '@/components/reader/readerPreferenceStorage.ts';
import type { ReaderPreferences } from '@/components/reader/readerPreferences.ts';
import { useEffect, useState, type Dispatch, type SetStateAction } from 'react';

/** The reader's appearance, read during the first render and written down as it changes. */
export const useReaderPreferences = (): [
  ReaderPreferences,
  Dispatch<SetStateAction<ReaderPreferences>>,
] => {
  // Lazily, so the navigator is built on the stored appearance rather than the
  // book opening on the defaults and reflowing a tick later.
  const [preferences, setPreferences] = useState(loadReaderPreferences);

  // On every change rather than once a book is open: a reader who nudges the
  // font size and closes the book has still expressed a preference.
  useEffect(() => {
    saveReaderPreferences(preferences);
  }, [preferences]);

  return [preferences, setPreferences];
};
