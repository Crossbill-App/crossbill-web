import type { NoteWithLinks } from '@/api/generated/model';
import { CardList } from '@/components/CardList.tsx';
import { UnlinkButton } from '@/components/buttons/UnlinkButton.tsx';
import { NoteCard } from '@/pages/BookPage/Notes/NoteCard';

interface LinkedNoteListProps {
  notes: NoteWithLinks[];
  onOpen: (note: NoteWithLinks) => void;
  onUnlink: (note: NoteWithLinks) => void;
  disabled: boolean;
}

/**
 * Notes linked to something, each with the control that breaks the link. Both
 * surfaces that show such a list render it through here, so the control cannot
 * end up worded one way beside a highlight and another beside a reflection.
 */
export const LinkedNoteList = ({ notes, onOpen, onUnlink, disabled }: LinkedNoteListProps) => (
  <CardList>
    {notes.map((note) => (
      <li key={note.id}>
        <NoteCard
          note={note}
          onClick={() => onOpen(note)}
          action={
            <UnlinkButton
              label="Remove link to this note"
              disabled={disabled}
              onClick={() => onUnlink(note)}
            />
          }
        />
      </li>
    ))}
  </CardList>
);
