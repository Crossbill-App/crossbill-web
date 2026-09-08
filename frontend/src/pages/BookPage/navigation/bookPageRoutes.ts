import { useGetBookDetails } from '@/api/generated/books/books.ts';
import {
  ChapterListIcon,
  FlashcardsIcon,
  HighlightsIcon,
  NotesIcon,
  ReaderIcon,
  ReflectionIcon,
  StatisticsIcon,
} from '@/theme/Icons.tsx';
import type { SvgIconComponent } from '@mui/icons-material';

type BookPageRoute =
  | '/book/$bookId/read'
  | '/book/$bookId/structure'
  | '/book/$bookId/highlights'
  | '/book/$bookId/flashcards'
  | '/book/$bookId/notes'
  | '/book/$bookId/reflection'
  | '/book/$bookId/statistics';

/**
 * What each of the book's tabs is called. The desktop nav, the mobile nav and
 * the page's own title all read this, so a tab cannot be named one thing in the
 * nav and another on the page it opens.
 */
export const BOOK_PAGE_LABELS = {
  read: 'Read',
  structure: 'Structure',
  highlights: 'Highlights',
  flashcards: 'Flashcards',
  notes: 'Notes',
  reflection: 'Reflection',
  statistics: 'Statistics',
} as const;

type BookPageSegment = keyof typeof BOOK_PAGE_LABELS;

export interface BookPageRouteConfig {
  to: BookPageRoute;
  segment: BookPageSegment;
  icon: SvgIconComponent;
  /**
   * When true, the route is tucked into the "More" overflow menu on the mobile
   * bottom navigation instead of getting a top-level tab. Desktop nav shows all
   * routes regardless.
   */
  overflow?: boolean;
  /**
   * When true, the route is only offered for a book that has an EPUB behind
   * it. There is nothing to read in the browser without one, and a tab that
   * can only lead to an empty state is worse than no tab.
   */
  needsPublication?: boolean;
}

export const BOOK_PAGE_ROUTES: BookPageRouteConfig[] = [
  {
    to: '/book/$bookId/read',
    segment: 'read',
    icon: ReaderIcon,
    needsPublication: true,
  },
  {
    to: '/book/$bookId/structure',
    segment: 'structure',
    icon: ChapterListIcon,
  },
  {
    to: '/book/$bookId/highlights',
    segment: 'highlights',
    icon: HighlightsIcon,
  },
  {
    to: '/book/$bookId/flashcards',
    segment: 'flashcards',
    icon: FlashcardsIcon,
    overflow: true,
  },
  {
    to: '/book/$bookId/notes',
    segment: 'notes',
    icon: NotesIcon,
  },
  {
    to: '/book/$bookId/reflection',
    segment: 'reflection',
    icon: ReflectionIcon,
    overflow: true,
  },
  {
    to: '/book/$bookId/statistics',
    segment: 'statistics',
    icon: StatisticsIcon,
    overflow: true,
  },
];

/**
 * The tabs this particular book actually has.
 *
 * Everything but the reader is offered for every book. The reader needs an
 * EPUB, and while it is unknown whether there is one the tab stays hidden —
 * appearing late is a smaller surprise than appearing and then vanishing under
 * the pointer.
 *
 * `has_ebook` comes from the book-details query the page has already run, so
 * this costs nothing. It used to be inferred from whether the Readium manifest
 * answered or 404'd, which parsed a whole publication server-side to decide
 * whether to draw a tab.
 */
export const useBookPageRoutes = (bookId: number): BookPageRouteConfig[] => {
  const { data: book } = useGetBookDetails(bookId);
  return BOOK_PAGE_ROUTES.filter((route) => !route.needsPublication || book?.has_ebook === true);
};
