import type { Note, NoteWithLinks } from '@/api/generated/model';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { DialogToolbar } from '@/components/dialogs/DialogToolbar.tsx';
import { NoteDialogs } from '@/pages/BookPage/Notes/NoteDialogs';
import { LinkedNoteList } from '@/pages/BookPage/Notes/components/LinkedNoteList.tsx';
import { NotePickerDialog } from '@/pages/BookPage/Notes/components/NotePickerDialog.tsx';
import { useNoteDialogs } from '@/pages/BookPage/Notes/hooks/useNoteDialogs';
import { AddIcon, LinkIcon } from '@/theme/Icons.tsx';
import { Box, Button } from '@mui/material';
import { compact, includes } from 'lodash';
import { useState } from 'react';

interface ReflectionNotesSectionProps {
  bookId: number;
  /** Currently linked note ids (the reflection's Q2 links). */
  noteIds: number[];
  /** All notes for the book, already cached by the page. */
  allNotes: NoteWithLinks[];
  /** Persist a new set of linked note ids (fires the reflection upsert). */
  onChange: (noteIds: number[]) => void;
  disabled?: boolean;
}

/**
 * Links the reader's term/concept notes to the "What does it say in detail?"
 * answer. Unlike the note-detail modals, link changes are written to the
 * reflection (its `note_ids` array), not to the notes themselves.
 */
export const ReflectionNotesSection = ({
  bookId,
  noteIds,
  allNotes,
  onChange,
  disabled = false,
}: ReflectionNotesSectionProps) => {
  const noteDialogs = useNoteDialogs({ syncToUrl: false });
  const [pickerOpen, setPickerOpen] = useState(false);

  const notesById = new Map(allNotes.map((note) => [note.id, note]));
  const linkedNotes = compact(noteIds.map((id) => notesById.get(id)));

  const handleUnlink = (noteId: number) => {
    onChange(noteIds.filter((id) => id !== noteId));
  };

  const handleLink = (note: NoteWithLinks) => {
    setPickerOpen(false);
    if (includes(noteIds, note.id)) return;
    onChange([...noteIds, note.id]);
  };

  const handleCreated = (note: Note) => {
    if (includes(noteIds, note.id)) return;
    onChange([...noteIds, note.id]);
  };

  return (
    <Box>
      <DialogToolbar sx={{ mb: 2 }}>
        <Button
          variant="outlined"
          size="small"
          startIcon={<LinkIcon />}
          onClick={() => setPickerOpen(true)}
          disabled={disabled}
        >
          Link existing note
        </Button>
        <Button
          variant="outlined"
          size="small"
          startIcon={<AddIcon />}
          onClick={noteDialogs.openCreate}
          disabled={disabled}
        >
          Add note
        </Button>
      </DialogToolbar>
      {linkedNotes.length === 0 && <EmptyStateText>No notes linked yet.</EmptyStateText>}
      <LinkedNoteList
        notes={linkedNotes}
        onOpen={noteDialogs.openView}
        onUnlink={(note) => handleUnlink(note.id)}
        disabled={disabled}
      />
      <NoteDialogs controller={noteDialogs} onCreated={handleCreated} />
      <NotePickerDialog
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        bookId={bookId}
        target="reflection"
        onSelect={handleLink}
      />
    </Box>
  );
};
