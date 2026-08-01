import { useDeleteHighlights } from '@/api/generated/highlights/highlights.ts';
import type { Bookmark, TagInBook } from '@/api/generated/model';
import { FadeInOut } from '@/components/animations/FadeInOut.tsx';
import { CommonDialog } from '@/components/dialogs/CommonDialog.tsx';
import { CommonDialogHorizontalNavigation } from '@/components/dialogs/CommonDialogHorizontalNavigation.tsx';
import { CommonDialogTitle } from '@/components/dialogs/CommonDialogTitle.tsx';
import { ConfirmationDialog } from '@/components/dialogs/ConfirmationDialog.tsx';
import { ProgressBar } from '@/components/dialogs/ProgressBar.tsx';
import { useDialogHorizontalNavigation } from '@/components/dialogs/useDialogHorizontalNavigation.ts';
import { TagInput } from '@/components/inputs/TagInput.tsx';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { useImmediateTagMutation } from '@/pages/BookPage/Highlights/HighlightViewDialog/hooks/useImmediateTagMutation.ts';
import type { HighlightDialogController } from '@/pages/BookPage/Highlights/hooks/useHighlightDialog.ts';
import { Box, Button, Stack } from '@mui/material';
import { useState } from 'react';
import { HighlightContent } from '../../common/HighlightContent.tsx';
import { HighlightTabs } from './components/HighlightTabs.tsx';
import { LabelEditorPopover } from './components/LabelEditorPopover.tsx';
import { Toolbar } from './components/Toolbar.tsx';

interface HighlightViewDialogProps {
  controller: HighlightDialogController;
  bookId: number;
  availableTags: TagInBook[];
  bookmarksByHighlightId: Record<number, Bookmark>;
}

export const HighlightViewDialog = ({
  controller,
  bookId,
  availableTags,
  bookmarksByHighlightId,
}: HighlightViewDialogProps) => {
  const cache = useCacheEvents();
  const mutationErrorHandler = useMutationErrorHandler();
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [labelAnchorEl, setLabelAnchorEl] = useState<HTMLElement | null>(null);

  // Callers render this dialog only while a highlight is active
  const highlight = controller.activeItem!;
  const open = controller.activeId !== null;

  const currentBookmark = bookmarksByHighlightId[highlight.id] ?? undefined;

  const { isProcessing, currentTags, updateTagList } = useImmediateTagMutation({
    bookId,
    highlightId: highlight.id,
    initialTags: highlight.tags,
  });

  const { hasNavigation, hasPrevious, hasNext, handlePrevious, handleNext, swipeHandlers } =
    useDialogHorizontalNavigation({
      open,
      currentIndex: controller.activeIndex,
      totalCount: controller.totalCount,
      onNavigate: controller.navigateToIndex,
    });

  const deleteHighlightMutation = useDeleteHighlights({
    mutation: {
      onSuccess: () => {
        cache.bookChanged(bookId);
        controller.close();
      },
      onError: mutationErrorHandler('delete highlight'),
    },
  });

  const handleDelete = () => {
    setDeleteConfirmOpen(true);
  };

  const handleConfirmDelete = () => {
    setDeleteConfirmOpen(false);
    deleteHighlightMutation.mutate({
      bookId,
      data: { highlight_ids: [highlight.id] },
    });
  };

  const handleClose = () => {
    cache.tagsChanged(bookId);
    controller.close(highlight.id);
  };

  const handleLabelClick = (event: React.MouseEvent<HTMLElement>) => {
    if (highlight.label?.highlight_style_id) {
      setLabelAnchorEl(event.currentTarget);
    }
  };

  const isLoading = deleteHighlightMutation.isPending;

  const titleText = highlight.chapter ? `${highlight.chapter}` : 'Highlight';
  const title = <CommonDialogTitle>{titleText}</CommonDialogTitle>;

  // Shared content for both layouts
  const renderContent = () => (
    <Box key={highlight.id}>
      <Stack
        sx={{
          gap: 2,
        }}
      >
        <Toolbar
          highlightId={highlight.id}
          bookId={bookId}
          highlightText={highlight.text}
          bookmark={currentBookmark}
          onDelete={handleDelete}
          disabled={isLoading}
        />
        <TagInput
          value={currentTags}
          onChange={updateTagList}
          availableTags={availableTags}
          isProcessing={isProcessing}
          disabled={isLoading}
        />
        <HighlightTabs highlight={highlight} bookId={bookId} disabled={isLoading} />
      </Stack>
    </Box>
  );

  return (
    <CommonDialog
      open={open}
      onClose={handleClose}
      maxWidth="md"
      isLoading={isLoading}
      title={title}
      headerElement={
        hasNavigation ? (
          <ProgressBar currentIndex={controller.activeIndex} totalCount={controller.totalCount} />
        ) : undefined
      }
      footerActions={
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', width: '100%' }}>
          <Button onClick={handleClose} disabled={isLoading}>
            Close
          </Button>
        </Box>
      }
    >
      <CommonDialogHorizontalNavigation
        hasNavigation={hasNavigation}
        hasPrevious={hasPrevious}
        hasNext={hasNext}
        onPrevious={handlePrevious}
        onNext={handleNext}
        swipeHandlers={swipeHandlers}
        disabled={isLoading}
      >
        <FadeInOut ekey={highlight.id}>
          <HighlightContent highlight={highlight} onLabelClick={handleLabelClick} />
        </FadeInOut>
        {renderContent()}
      </CommonDialogHorizontalNavigation>

      <ConfirmationDialog
        open={deleteConfirmOpen}
        onClose={() => setDeleteConfirmOpen(false)}
        onConfirm={handleConfirmDelete}
        title="Delete Highlight"
        message="Are you sure you want to delete this highlight?"
        confirmText="Delete"
        confirmColor="error"
        isLoading={isLoading}
      />

      {highlight.label?.highlight_style_id && (
        <LabelEditorPopover
          anchorEl={labelAnchorEl}
          open={!!labelAnchorEl}
          onClose={() => setLabelAnchorEl(null)}
          styleId={highlight.label.highlight_style_id}
          currentLabel={highlight.label.text}
          currentColor={highlight.label.ui_color}
          bookId={bookId}
        />
      )}
    </CommonDialog>
  );
};
