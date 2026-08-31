/**
 * Centralized icon exports with semantic Crossbill naming.
 * All MUI icons are re-exported here with domain-specific names.
 */

// Navigation icons
export {
  ArrowBack as ArrowBackIcon,
  ArrowForward as ArrowForwardIcon,
  Close as CloseIcon,
  ExpandMore as ExpandMoreIcon,
  OpenInNew as ExternalLinkIcon,
  FilterList as FilterListIcon,
  MoreVert as ManageIcon,
  MoreHoriz as MoreIcon,
  KeyboardArrowUp as ScrollToTopIcon,
  Search as SearchIcon,
} from '@mui/icons-material';

// Content icons
export {
  MenuBook as BookCoverIcon,
  Bookmark as BookmarkFilledIcon,
  BookmarkBorder as BookmarkIcon,
  List as ChapterListIcon,
  StyleOutlined as FlashcardsIcon,
  // One glyph, one name: the quote mark on a card and the Highlights nav item
  // are the same idea, and `MenuBook` now means only "a book".
  FormatQuote as HighlightsIcon,
  Notes as NotesIcon,
  PaletteOutlined as PaletteIcon,
  AutoStories as ReadingSessionIcon,
  Psychology as ReflectionIcon,
  Equalizer as StatisticsIcon,
  LocalOffer as TagIcon,
} from '@mui/icons-material';

// Action icons
export {
  AutoAwesome as AIIcon,
  Check as AcceptIcon,
  Add as AddIcon,
  ContentCopy as CopyIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  PlaylistAdd as EditTagsIcon,
  Link as LinkIcon,
  LinkOff as LinkOffIcon,
  NoteAdd as NoteAddIcon,
  Refresh as RegenerateIcon,
  Close as RejectIcon,
  Replay as RetryIcon,
  Check as SelectedIcon,
  Send as SendIcon,
  SwapVert as SortIcon,
} from '@mui/icons-material';

// User/System icons
export {
  AccountCircle as AccountIcon,
  Logout as LogoutIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';

// Device sync icons
export { PhonelinkOff as NotOnDeviceIcon } from '@mui/icons-material';

// Reading stage icons
export { Check as ReadingDoneIcon, Timelapse as ReadingInProgressIcon } from '@mui/icons-material';

// Date/Time icons
export { CalendarMonth as DateIcon } from '@mui/icons-material';
