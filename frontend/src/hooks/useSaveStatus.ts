import { useCallback, useEffect, useRef, useState } from 'react';

export type SaveStatus = 'idle' | 'saving' | 'saved';

/** Long enough to be read, short enough not to linger over the next edit. */
const SAVED_VISIBLE_MS = 2000;

export interface SaveStatusHandle {
  status: SaveStatus;
  saving: () => void;
  saved: () => void;
  /** Back to showing nothing — after a failure, or when the edit is dropped. */
  reset: () => void;
}

/**
 * Drives a `SavedIndicator` for an autosaving field: "Saving..." while the
 * mutation is in flight, "Saved" for a moment after it lands, nothing
 * otherwise.
 *
 * Failures are already reported by the error snackbar, so they return the
 * marker to idle rather than claiming a state of their own.
 */
export const useSaveStatus = (): SaveStatusHandle => {
  const [status, setStatus] = useState<SaveStatus>('idle');
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => () => clearTimeout(timer.current), []);

  const saving = useCallback(() => {
    clearTimeout(timer.current);
    setStatus('saving');
  }, []);

  const saved = useCallback(() => {
    clearTimeout(timer.current);
    setStatus('saved');
    timer.current = setTimeout(() => setStatus('idle'), SAVED_VISIBLE_MS);
  }, []);

  const reset = useCallback(() => {
    clearTimeout(timer.current);
    setStatus('idle');
  }, []);

  return { status, saving, saved, reset };
};
