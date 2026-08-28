import { useRef, useState, type ChangeEvent, type KeyboardEvent } from 'react';
import { useResetOnChange } from './useResetOnChange';

interface UseCommitOnBlurOptions {
  /** The value the server holds. */
  saved: string;
  /** Called when the field is left carrying a value the server does not have. */
  onCommit: (value: string) => void;
  /** Called when the field is left, changed or not. */
  onBlur?: () => void;
  /** Called when Escape reverts the field. */
  onCancel?: () => void;
  /** Enter commits, Shift+Enter inserts a newline. Off for free-form prose. */
  submitOnEnter?: boolean;
}

export interface CommitOnBlurField {
  value: string;
  isDirty: boolean;
  /** Drop the local text and show `saved` again. */
  revert: () => void;
  /** After a failed save: let leaving the field commit the same value again. */
  allowRecommit: () => void;
  inputProps: {
    value: string;
    onChange: (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
    onFocus: () => void;
    onBlur: () => void;
    onKeyDown: (event: KeyboardEvent<HTMLDivElement>) => void;
  };
}

/**
 * A text field whose local text is committed when the reader leaves it.
 *
 * The caller keeps everything domain-shaped — which mutation runs, what an
 * empty value means, how a failure is shown.
 */
export const useCommitOnBlur = ({
  saved,
  onCommit,
  onBlur,
  onCancel,
  submitOnEnter = true,
}: UseCommitOnBlurOptions): CommitOnBlurField => {
  // The text on screen while a save is in flight; `null` means the server's
  // value is what is shown.
  const [draft, setDraft] = useState<string | null>(null);
  const isFocused = useRef(false);
  // The value last handed to `onCommit`, so leaving the field again before the
  // refetch lands does not save it twice — which for a create would mean two
  // records rather than one.
  const committed = useRef<string | null>(null);
  // Set by Escape, so the blur it causes does not commit the reverted text.
  const cancelled = useRef(false);

  const revert = () => {
    setDraft(null);
    committed.current = null;
  };

  // While the field has focus the reader's text wins. Once they have left, the
  // refetched value takes over — dropping the draft any earlier would flash the
  // old text back between the save and the refetch.
  useResetOnChange([saved], () => {
    if (!isFocused.current) revert();
  });

  const value = draft ?? saved;

  const commit = () => {
    if (value === saved || value === committed.current) return;
    committed.current = value;
    onCommit(value);
  };

  return {
    value,
    isDirty: value !== saved,
    revert,
    allowRecommit: () => {
      committed.current = null;
    },
    inputProps: {
      value,
      onChange: (event) => {
        cancelled.current = false;
        committed.current = null;
        setDraft(event.target.value);
      },
      onFocus: () => {
        isFocused.current = true;
      },
      onBlur: () => {
        isFocused.current = false;
        if (cancelled.current) {
          cancelled.current = false;
        } else {
          commit();
        }
        onBlur?.();
      },
      onKeyDown: (event) => {
        if (submitOnEnter && event.key === 'Enter' && !event.shiftKey) {
          // Blur rather than commit here, so the value is saved once whether
          // the reader finishes with Enter or by clicking away.
          event.preventDefault();
          (event.target as HTMLElement).blur();
        } else if (event.key === 'Escape') {
          // A dialog hosting the field closes on Escape; reverting the text is
          // what this Escape means.
          event.stopPropagation();
          cancelled.current = true;
          revert();
          onCancel?.();
        }
      },
    },
  };
};
