import type { Highlight, NoteLinkedChapter, NoteWithLinks } from '@/api/generated/model';
import { CardList } from '@/components/CardList.tsx';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { UnlinkButton } from '@/components/buttons/UnlinkButton.tsx';
import { HighlightCard } from '@/components/cards/HighlightCard.tsx';
import { DialogTabs, type DialogTabItem } from '@/components/dialogs/DialogTabs.tsx';
import { NoteFlashcardSection } from '@/pages/BookPage/Notes/components/NoteFlashcardSection.tsx';
import { useNoteCountsByHighlight } from '@/pages/BookPage/Notes/hooks/useNoteCountsByHighlight.ts';
import { Box, List, ListItem, ListItemButton, ListItemText } from '@mui/material';
import { useTranslation } from 'react-i18next';

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
  const { t } = useTranslation();
  const noteCountByHighlightId = useNoteCountsByHighlight();

  const tabs: DialogTabItem[] = [
    {
      key: 'highlights',
      label: t('common.entities.highlights'),
      count: highlights.length,
      content:
        highlights.length === 0 ? (
          <EmptyStateText>{t('notes.noteTabs.noHighlights')}</EmptyStateText>
        ) : (
          <CardList>
            {highlights.map((highlight) => (
              <Box component="li" key={highlight.id} sx={{ position: 'relative' }}>
                <HighlightCard
                  highlight={highlight}
                  noteCount={noteCountByHighlightId[highlight.id]}
                  onOpenModal={onOpenHighlight}
                />
                {onUnlinkHighlight && (
                  <UnlinkButton
                    label={t('notes.noteTabs.unlinkHighlight')}
                    disabled={disabled}
                    onClick={() => onUnlinkHighlight(highlight.id)}
                    sx={{ position: 'absolute', bottom: 8, right: 8 }}
                  />
                )}
              </Box>
            ))}
          </CardList>
        ),
    },
    {
      key: 'chapters',
      label: t('common.entities.chapters'),
      count: chapters.length,
      content:
        chapters.length === 0 ? (
          <EmptyStateText>{t('notes.noteTabs.noChapters')}</EmptyStateText>
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
                      label={t('notes.noteTabs.unlinkChapter')}
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
      label: t('common.entities.flashcards'),
      count: note.flashcards?.length ?? 0,
      content: <NoteFlashcardSection note={note} bookId={bookId} disabled={disabled} />,
    },
  ];

  return <DialogTabs tabs={tabs} />;
};
