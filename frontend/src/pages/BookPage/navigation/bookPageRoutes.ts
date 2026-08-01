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

export interface BookPageRouteConfig {
  to: BookPageRoute;
  segment: string;
  label: string;
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
    label: 'Structure',
    icon: ChapterListIcon,
  },
  {
    to: '/book/$bookId/highlights',
    segment: 'highlights',
    label: 'Highlights',
    icon: HighlightsIcon,
  },
  {
    to: '/book/$bookId/flashcards',
    segment: 'flashcards',
    label: 'Flashcards',
    icon: FlashcardsIcon,
    overflow: true,
  },
  {
    to: '/book/$bookId/notes',
    segment: 'notes',
    label: 'Notes',
    icon: NotesIcon,
  },
  {
    to: '/book/$bookId/reflection',
    segment: 'reflection',
    label: 'Reflection',
    icon: ReflectionIcon,
    overflow: true,
  },
  {
    to: '/book/$bookId/sessions',
    segment: 'sessions',
    label: 'Sessions',
    icon: ReadingSessionIcon,
    overflow: true,
  },
];
