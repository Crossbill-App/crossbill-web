import type { Highlight, NoteLinkedChapter, NoteWithLinks } from '@/api/generated/model';
import { CardList } from '@/components/CardList.tsx';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { UnlinkButton } from '@/components/buttons/UnlinkButton.tsx';
import { HighlightCard } from '@/components/cards/HighlightCard.tsx';
import { DialogTabs, type DialogTabItem } from '@/components/dialogs/DialogTabs.tsx';
import { NoteFlashcardSection } from '@/pages/BookPage/Notes/components/NoteFlashcardSection.tsx';
import { Box, List, ListItem, ListItemButton, ListItemText } from '@mui/material';

interface NoteTabsProps {
  note: NoteWithLinks;
  bookId: number;
  highlights: Highlight[];
  chapters: NoteLinkedChapter[];
  onOpenHighlight: (highlightId: number) => void;
  onOpenChapter: (chapterId: number) => void;
  onUnlinkHighlight?: (highlightId: number) => void;
  onUnlinkChapter?: (chapterId: number) => void;
  disabled?: boolean;
}

/**
 * Tabs for a note's secondary content: linked highlights, linked chapters and
 * the note's flashcards. The Highlights tab reuses the shared `HighlightCard`;
 * the Chapters tab lists clickable rows — mirroring the tabbed composition of
 * `HighlightViewDialog` and `ChapterDetailDialog`.
 */
export const NoteTabs = ({
  note,
  bookId,
  highlights,
  chapters,
  onOpenHighlight,
  onOpenChapter,
  onUnlinkHighlight,
  onUnlinkChapter,
  disabled = false,
}: NoteTabsProps) => {
  const tabs: DialogTabItem[] = [
    {
      key: 'highlights',
      label: 'Highlights',
      count: highlights.length,
      content:
        highlights.length === 0 ? (
          <EmptyStateText>No highlights linked to this note.</EmptyStateText>
        ) : (
          <CardList>
            {highlights.map((highlight) => (
              <Box component="li" key={highlight.id} sx={{ position: 'relative' }}>
                <HighlightCard highlight={highlight} onOpenModal={onOpenHighlight} />
                {onUnlinkHighlight && (
                  <UnlinkButton
                    title="Remove link to this highlight"
                    disabled={disabled}
                    onClick={() => onUnlinkHighlight(highlight.id)}
                    sx={{ position: 'absolute', top: 8, right: 8 }}
                  />
                )}
              </Box>
            ))}
          </CardList>
        ),
    },
    {
      key: 'chapters',
      label: 'Chapters',
      count: chapters.length,
      content:
        chapters.length === 0 ? (
          <EmptyStateText>No chapters linked to this note.</EmptyStateText>
        ) : (
          <List disablePadding>
            {chapters.map((chapter) => (
              <ListItem
                key={chapter.id}
                disablePadding
                secondaryAction={
                  onUnlinkChapter && (
                    <UnlinkButton
                      edge="end"
                      title="Remove link to this chapter"
                      disabled={disabled}
                      onClick={() => onUnlinkChapter(chapter.id)}
                    />
                  )
                }
              >
                <ListItemButton onClick={() => onOpenChapter(chapter.id)}>
                  <ListItemText primary={chapter.name} />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        ),
    },
    {
      key: 'flashcards',
      label: 'Flashcards',
      count: note.flashcards?.length ?? 0,
      content: <NoteFlashcardSection note={note} bookId={bookId} disabled={disabled} />,
    },
  ];

  return <DialogTabs tabs={tabs} />;
};
