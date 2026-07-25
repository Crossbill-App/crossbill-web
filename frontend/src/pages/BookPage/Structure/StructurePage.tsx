import type { ChapterPrereadingResponse, ChapterWithHighlights } from '@/api/generated/model';
import { useGetNotesForBook } from '@/api/generated/notes/notes.ts';
import { useGetBookPrereading } from '@/api/generated/prereading/prereading';
import { useUrlEntityDialog } from '@/components/dialogs/useUrlEntityDialog.ts';
import { useBookPage } from '@/pages/BookPage/BookPageContext';
import { Box, Typography } from '@mui/material';
import { keyBy } from 'lodash';
import { useMemo } from 'react';
import { BatchPrereadingToolbar } from './BatchPrereadingToolbar';
import { ChapterAccordion } from './ChapterAccordion';
import { ChapterDetailDialog } from './ChapterDetailDialog/ChapterDetailDialog.tsx';

export const StructurePage = () => {
  const { book } = useBookPage();

  const { data: bookPrereading } = useGetBookPrereading(book.id);

  const prereadingByChapterId = useMemo(() => {
    const map: Record<number, ChapterPrereadingResponse> = {};
    if (bookPrereading?.items) {
      for (const item of bookPrereading.items) {
        map[item.chapter_id] = item;
      }
    }
    return map;
  }, [bookPrereading]);

  const { data: gistNotes } = useGetNotesForBook(book.id, {
    kind: 'gist',
  });

  const gistByChapterId = useMemo(() => {
    const map = new Map<number, string>();
    for (const note of gistNotes?.items ?? []) {
      if (note.chapter_ids.length === 0) continue;
      const chapterId = note.chapter_ids[0];
      if (!map.has(chapterId)) {
        map.set(chapterId, note.body);
      }
    }
    return map;
  }, [gistNotes]);

  const childrenByParentId = useMemo(() => {
    const map = new Map<number | null, ChapterWithHighlights[]>();
    for (const ch of book.chapters) {
      const key = ch.parent_id ?? null;
      const list = map.get(key) ?? [];
      list.push(ch);
      map.set(key, list);
    }
    return map;
  }, [book.chapters]);

  // Compute leaf chapters in document order (depth-first)
  const leafChapters = useMemo(() => {
    const result: ChapterWithHighlights[] = [];
    const collectLeaves = (parentId: number | null) => {
      const children = childrenByParentId.get(parentId) ?? [];
      for (const ch of children) {
        const hasChildren = (childrenByParentId.get(ch.id) ?? []).length > 0;
        if (hasChildren) {
          collectLeaves(ch.id);
        } else {
          result.push(ch);
        }
      }
    };
    collectLeaves(null);
    return result;
  }, [childrenByParentId]);

  const chapterDialog = useUrlEntityDialog<ChapterWithHighlights>({
    param: 'chapterId',
    items: leafChapters,
  });

  // Compute bookmarks map
  const bookmarksByHighlightId = useMemo(
    () => keyBy(book.bookmarks, 'highlight_id'),
    [book.bookmarks]
  );

  if (book.chapters.length === 0) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography variant="body1" color="text.secondary">
          No chapter structure available for this book.
        </Typography>
      </Box>
    );
  }

  const topLevelChapters = childrenByParentId.get(null) ?? [];

  const readingPosition = book.reading_position;

  const isChapterRead = (startPosition: { index: number } | null | undefined): boolean => {
    if (!readingPosition || !startPosition) return false;
    return readingPosition.index >= startPosition.index;
  };

  return (
    <>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', px: 1, pt: 1 }}>
        <BatchPrereadingToolbar bookId={book.id} />
      </Box>
      {topLevelChapters.map((chapter, index) => {
        const chapterIsRead = isChapterRead(chapter.start_position);
        const isLastChapter = index === topLevelChapters.length - 1;
        const nextIsRead = isLastChapter
          ? false
          : isChapterRead(topLevelChapters[index + 1].start_position);
        const chapterIsCurrent = chapterIsRead && !nextIsRead;

        return (
          <ChapterAccordion
            key={chapter.id}
            chapter={chapter}
            childrenByParentId={childrenByParentId}
            gistByChapterId={gistByChapterId}
            bookId={book.id}
            isRead={chapterIsRead}
            isCurrent={chapterIsCurrent}
            readingPosition={readingPosition}
            onChapterClick={chapterDialog.open}
          />
        );
      })}

      {chapterDialog.activeItem && (
        <ChapterDetailDialog
          controller={chapterDialog}
          bookId={book.id}
          prereadingByChapterId={prereadingByChapterId}
          bookmarksByHighlightId={bookmarksByHighlightId}
          availableTags={book.tags}
          bookFlashcards={book.book_flashcards}
        />
      )}
    </>
  );
};
