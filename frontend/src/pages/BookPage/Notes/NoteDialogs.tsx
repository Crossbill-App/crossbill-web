import type { Note } from '@/api/generated/model';

import { NoteEditorDialog } from './NoteEditorDialog';
import { NoteViewDialog } from './NoteViewDialog';
import type { NoteDialogsController } from './hooks/useNoteDialogs';

interface NoteDialogsProps {
  controller: NoteDialogsController;
  /** Pre-link created notes to these chapters (e.g. from the chapter section). */
  initialChapterIds?: number[];
  /** Pre-link created notes to these highlights (e.g. from the highlight dialog). */
  initialHighlightIds?: number[];
  /** Called with the created note after a successful create (not on update). */
  onCreated?: (note: Note) => void;
}

/**
 * Renders the note create editor and the note detail dialog for a `useNoteDialogs`
 * controller, so each surface (notes tab, chapter section, ...) only wires up the
 * triggers, not the dialogs. Editing/deleting an existing note lives inside
 * `NoteViewDialog`.
 *
 * Prev/next navigation is forwarded only when the controller knows the viewed
 * note's position in its `allNotes` list — a deep link to a note filtered out
 * of the current list still opens, just without navigation.
 */
export const NoteDialogs = ({
  controller,
  initialChapterIds,
  initialHighlightIds,
  onCreated,
}: NoteDialogsProps) => {
  const hasNavigation = controller.activeIndex >= 0 && controller.totalCount > 1;

  return (
    <>
      <NoteEditorDialog
        open={controller.editorOpen}
        onClose={controller.closeEditor}
        initialChapterIds={initialChapterIds}
        initialHighlightIds={initialHighlightIds}
        onCreated={onCreated}
      />
      {controller.activeId !== null && (
        <NoteViewDialog
          noteId={controller.activeId}
          onClose={controller.close}
          currentIndex={hasNavigation ? controller.activeIndex : undefined}
          totalCount={hasNavigation ? controller.totalCount : undefined}
          onNavigate={hasNavigation ? controller.navigateToIndex : undefined}
        />
      )}
    </>
  );
};
