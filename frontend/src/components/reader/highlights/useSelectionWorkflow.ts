/**
 * The way from a selection in the book to a highlight, including extending the
 * passage by a tap on a later page. Only one thing along it has to be held: the
 * engine remembers where an extension started, but not that a tap is still
 * awaited, and the bar saying so is the reader's only way out of it. Everything
 * else is read off the selection the book reports.
 */
import type { EbookLocation } from '@/components/reader/engine/EbookReader.ts';
import type { HighlightCreation } from '@/components/reader/highlights/useHighlightCreation.ts';
import type { EbookReaderState } from '@/components/reader/opening/useEbookReader.ts';
import { useResetOnChange } from '@/hooks/useResetOnChange.ts';
import { useState } from 'react';

export interface SelectionWorkflow {
  /** Whether a tap is awaited to say where the passage being extended ends. */
  isExtending: boolean;
  /** Drawn by the reader itself: a passage the browser has stopped showing as selected
   * would otherwise sit under the popover with nothing marking its words. */
  heldPassage: EbookLocation | null;
  /** Lets go of the selection and stores the passage it covered. */
  highlight: () => void;
  /** Asks the engine to carry the passage over to a tap yet to come. */
  extend: () => void;
  /** Lets the engine forget where the passage started. */
  stopExtending: () => void;
}

export const useSelectionWorkflow = (
  book: Pick<
    EbookReaderState,
    'selection' | 'clearSelection' | 'startSelectionExtension' | 'cancelSelectionExtension'
  >,
  creation: HighlightCreation
): SelectionWorkflow => {
  const [isExtending, setIsExtending] = useState(false);

  // A selection while a tap is awaited is the extended passage arriving.
  useResetOnChange([book.selection], () => {
    if (book.selection) setIsExtending(false);
  });

  const highlight = () => {
    const location = book.selection?.location;
    book.clearSelection();
    if (location) creation.create(location);
  };

  const extend = () => {
    book.startSelectionExtension();
    setIsExtending(true);
  };

  const stopExtending = () => {
    book.cancelSelectionExtension();
    setIsExtending(false);
  };

  return {
    isExtending,
    heldPassage: book.selection?.shownAsSelected === false ? book.selection.location : null,
    highlight,
    extend,
    stopExtending,
  };
};
