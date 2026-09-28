import auth from './auth.json';
import book from './book.json';
import common from './common.json';
import components from './components.json';
import flashcards from './flashcards.json';
import highlights from './highlights.json';
import landing from './landing.json';
import layout from './layout.json';
import library from './library.json';
import notes from './notes.json';
import reader from './reader.json';
import reflection from './reflection.json';
import search from './search.json';
import settings from './settings.json';
import structure from './structure.json';

/**
 * English copy, the source every other language translates from.
 *
 * One file per area of the app; its top-level key is the file name, and keys
 * nest by screen and component so a key says where its text appears
 * (`highlights.viewDialog.deleteConfirm.title`). Text that means the same
 * thing wherever it appears — button verbs, entity names, fallbacks — is
 * defined once in `common.json` and reused, never copied into an area file.
 */
export const en = {
  common,
  auth,
  landing,
  layout,
  components,
  library,
  search,
  settings,
  book,
  highlights,
  notes,
  reflection,
  flashcards,
  structure,
  reader,
};
