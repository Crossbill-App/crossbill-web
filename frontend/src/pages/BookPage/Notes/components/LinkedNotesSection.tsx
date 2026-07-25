import type { NoteWithLinks } from '@/api/generated/model';
import { CardList } from '@/components/CardList.tsx';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { UnlinkButton } from '@/components/buttons/UnlinkButton.tsx';
import { DialogToolbar } from '@/components/dialogs/DialogToolbar.tsx';
import { NoteCard } from '@/pages/BookPage/Notes/NoteCard';
import { NoteDialogs } from '@/pages/BookPage/Notes/NoteDialogs';
import { NotePickerDialog } from '@/pages/BookPage/Notes/components/NotePickerDialog.tsx';
import { useNoteDialogs } from '@/pages/BookPage/Notes/hooks/useNoteDialogs';
import { useNoteLinks } from '@/pages/BookPage/Notes/hooks/useNoteLinks';
import { AddIcon, LinkIcon } from '@/theme/Icons.tsx';
import { Box, Button } from '@mui/material';
import { useState } from 'react';

export type NoteLinkTarget =
  | { kind: 'highlight'; id: number; chapterId?: number | null }
  | { kind: 'chapter'; id: number };

interface LinkedNotesSectionProps {
  bookId: number;
  /** Entity the listed notes are linked to; new notes are pre-linked to it. */
  target: NoteLinkTarget;
  /** Notes linked to the target; the query lives in the caller for the tab count. */
  notes: NoteWithLinks[];
  isLoading: boolean;
  disabled?: boolean;
}

/**
 * Notes tab of the entity detail modals (highlight, chapter): lists notes
 * linked to the target and offers creating a new pre-linked note, linking an
 * existing one, or removing a link. Link changes invalidate the notes-for-book
 * query (prefix match), so the filtered list here refreshes immediately.
 */
export const LinkedNotesSection = ({
  bookId,
  target,
  notes,
  isLoading,
  disabled = false,
}: LinkedNotesSectionProps) => {
  const noteDialogs = useNoteDialogs({ syncToUrl: false });
  const [pickerOpen, setPickerOpen] = useState(false);
  const noteLinks = useNoteLinks({ bookId });

  const isDisabled = disabled || noteLinks.isPending;

  const handleUnlink = (note: NoteWithLinks) => {
    if (target.kind === 'highlight') {
      noteLinks.unlinkHighlight(note, target.id);
    } else {
      noteLinks.unlinkChapter(note, target.id);
    }
  };

  const handleLink = (note: NoteWithLinks) => {
    if (target.kind === 'highlight') {
      noteLinks.linkHighlight(note, target.id, { onSuccess: () => setPickerOpen(false) });
    } else {
      noteLinks.linkChapter(note, target.id, { onSuccess: () => setPickerOpen(false) });
    }
  };

  const initialChapterIds =
    target.kind === 'chapter' ? [target.id] : target.chapterId ? [target.chapterId] : [];

  return (
    <Box>
      <DialogToolbar sx={{ mb: 2 }}>
        <Button
          variant="outlined"
          size="small"
          startIcon={<LinkIcon />}
          onClick={() => setPickerOpen(true)}
          disabled={isDisabled}
        >
          Link existing note
        </Button>
        <Button
          variant="outlined"
          size="small"
          startIcon={<AddIcon />}
          onClick={noteDialogs.openCreate}
          disabled={isDisabled}
        >
          Add note
        </Button>
      </DialogToolbar>
      {isLoading && <Spinner />}
      {!isLoading && notes.length === 0 && (
        <EmptyStateText>No notes linked to this {target.kind}.</EmptyStateText>
      )}
      <CardList>
        {notes.map((note) => (
          <li key={note.id}>
            <NoteCard
              note={note}
              onClick={() => noteDialogs.openView(note)}
              action={
                <UnlinkButton
                  title={`Unlink from ${target.kind}`}
                  disabled={isDisabled}
                  onClick={() => handleUnlink(note)}
                />
              }
            />
          </li>
        ))}
      </CardList>
      <NoteDialogs
        controller={noteDialogs}
        initialChapterIds={initialChapterIds}
        initialHighlightIds={target.kind === 'highlight' ? [target.id] : undefined}
      />
      <NotePickerDialog
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        bookId={bookId}
        title={target.kind === 'highlight' ? 'Add highlight to note' : 'Add chapter to note'}
        onSelect={handleLink}
      />
    </Box>
  );
};
