import { useCallback, useEffect, useRef } from 'react';

let stack: symbol[] = [];

/**
 * Registers an open dialog as the topmost one for as long as it stays open,
 * and reports whether it still is.
 *
 * `CommonDialog` registers every dialog it renders, paged or not: a dialog
 * with nothing of its own to page must still shadow the ones beneath it, or
 * their arrow-key handler stays topmost and pages content the reader can no
 * longer see (#620). Registering in the shell rather than at each consumer is
 * what keeps that true for dialogs added later.
 */
/**
 * Whether any dialog is open anywhere in the app.
 *
 * For window-level keyboard handlers that belong to the *page*, which have to
 * stand down while a modal is up: a dialog covers what is underneath it, so the
 * keys underneath are not the reader's to act on. `CommonDialog` registers
 * every dialog it renders, so this keeps answering correctly for dialogs added
 * later — the same reason the stack is maintained in the shell rather than at
 * each consumer.
 */
export const isAnyDialogOpen = () => stack.length > 0;

export const useDialogStackEntry = (open: boolean) => {
  const idRef = useRef(Symbol());

  useEffect(() => {
    if (!open) return;

    const id = idRef.current;
    stack.push(id);
    return () => {
      stack = stack.filter((entry) => entry !== id);
    };
  }, [open]);

  return useCallback(() => stack[stack.length - 1] === idRef.current, []);
};
