import {
  ChapterListIcon,
  FlashcardsIcon,
  HighlightsIcon,
  NotesIcon,
  ReadingSessionIcon,
  ReflectionIcon,
} from '@/theme/Icons.tsx';
import type { SvgIconComponent } from '@mui/icons-material';

type BookPageRoute =
  | '/book/$bookId/structure'
  | '/book/$bookId/highlights'
  | '/book/$bookId/flashcards'
  | '/book/$bookId/notes'
  | '/book/$bookId/reflection'
  | '/book/$bookId/sessions';

/**
 * What each of the book's tabs is called. The desktop nav, the mobile nav and
 * the page's own title all read this, so a tab cannot be named one thing in the
 * nav and another on the page it opens.
 *
 * A key is the route segment, not the name: the statistics tab still lives at
 * `/sessions`, where the sessions list was all it held.
 */
export const BOOK_PAGE_LABELS = {
  structure: 'Structure',
  highlights: 'Highlights',
  flashcards: 'Flashcards',
  notes: 'Notes',
  reflection: 'Reflection',
  sessions: 'Statistics',
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
}

export const BOOK_PAGE_ROUTES: BookPageRouteConfig[] = [
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
    to: '/book/$bookId/sessions',
    segment: 'sessions',
    icon: ReadingSessionIcon,
    overflow: true,
  },
];
