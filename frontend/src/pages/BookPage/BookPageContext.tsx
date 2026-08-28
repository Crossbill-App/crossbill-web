import type { BookDetails } from '@/api/generated/model';
import { createContext, useContext } from 'react';

interface BookPageContextValue {
  book: BookDetails;
  isDesktop: boolean;
  // Portal element to add content to the left side bar below navigation
  leftSidebarEl: HTMLDivElement | null;
  // Portal element for the right rail. The shell reserves its column on every
  // tab, so a tab that has nothing to put there leaves it empty rather than
  // widening its content into it.
  rightSidebarEl: HTMLDivElement | null;
  // Portal element to add fabs under the scroll to top button
  fabContainerEl: HTMLDivElement | null;
}

const BookPageContext = createContext<BookPageContextValue | null>(null);

export const BookPageProvider = BookPageContext.Provider;

export const useBookPage = (): BookPageContextValue => {
  const context = useContext(BookPageContext);
  if (!context) {
    throw new Error('useBookPage must be used within a BookPageProvider');
  }
  return context;
};
