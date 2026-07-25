import { useCreateBookmark, useDeleteBookmark } from '@/api/generated/bookmarks/bookmarks.ts';
import type { Bookmark } from '@/api/generated/model';
import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip.tsx';
import { DialogToolbar } from '@/components/dialogs/DialogToolbar.tsx';
import { useBookMutationHelpers } from '@/hooks/useBookMutationHelpers.ts';
import {
  BookmarkFilledIcon,
  BookmarkIcon,
  CopyIcon,
  DeleteIcon,
  LinkIcon,
} from '@/theme/Icons.tsx';
import { copyUrlWithSearchParam } from '@/utils/clipboard.ts';
import { useState } from 'react';

interface ToolbarProps {
  highlightId: number;
  bookId: number;
  highlightText: string;
  bookmark?: Bookmark;
  onDelete: () => void;
  disabled?: boolean;
}

export const Toolbar = ({
  highlightId,
  bookId,
  highlightText,
  bookmark,
  onDelete,
  disabled = false,
}: ToolbarProps) => {
  const { handleBookmarkToggle, isProcessing } = useBookmarkMutations(
    bookmark,
    bookId,
    highlightId
  );

  // Copy a link that works from any context: `highlightId` is only a validated
  // search param on the highlights route, so build the URL on that route —
  // copying the current URL from e.g. the chapter dialog would be a dead link.
  const handleCopyLink = async () => {
    await copyUrlWithSearchParam(
      'highlightId',
      highlightId,
      `${window.location.origin}/book/${bookId}/highlights`
    );
  };

  const handleCopyContent = async () => {
    await navigator.clipboard.writeText(highlightText);
  };

  const isDisabled = disabled || isProcessing;

  return (
    <DialogToolbar>
      <IconButtonWithTooltip
        title="Copy link"
        onClick={handleCopyLink}
        disabled={isDisabled}
        ariaLabel="Copy link to highlight"
        icon={<LinkIcon />}
      />
      <IconButtonWithTooltip
        title="Copy highlight content"
        onClick={handleCopyContent}
        disabled={isDisabled}
        ariaLabel="Copy highlight text"
        icon={<CopyIcon />}
      />
      <IconButtonWithTooltip
        title={bookmark ? 'Remove bookmark' : 'Add bookmark'}
        onClick={handleBookmarkToggle}
        disabled={isDisabled}
        ariaLabel={bookmark ? 'Remove bookmark' : 'Add bookmark'}
        icon={bookmark ? <BookmarkFilledIcon /> : <BookmarkIcon />}
      />
      <IconButtonWithTooltip
        title="Delete highlight"
        onClick={onDelete}
        disabled={isDisabled}
        ariaLabel="Delete highlight"
        icon={<DeleteIcon />}
      />
    </DialogToolbar>
  );
};

const useBookmarkMutations = (
  bookmark: Bookmark | undefined,
  bookId: number,
  highlightId: number
) => {
  const { mutationErrorHandler, invalidateBookDetails } = useBookMutationHelpers(bookId);
  const [isProcessing, setIsProcessing] = useState(false);

  const createBookmarkMutation = useCreateBookmark({
    mutation: {
      onSuccess: invalidateBookDetails,
      onError: mutationErrorHandler('create bookmark'),
    },
  });

  const deleteBookmarkMutation = useDeleteBookmark({
    mutation: {
      onSuccess: invalidateBookDetails,
      onError: mutationErrorHandler('delete bookmark'),
    },
  });

  const handleBookmarkToggle = async () => {
    setIsProcessing(true);
    try {
      if (bookmark) {
        // Remove bookmark
        await deleteBookmarkMutation.mutateAsync({
          bookId,
          bookmarkId: bookmark.id,
        });
      } else {
        // Create bookmark
        await createBookmarkMutation.mutateAsync({
          bookId,
          data: { highlight_id: highlightId },
        });
      }
    } finally {
      setIsProcessing(false);
    }
  };

  return {
    isProcessing,
    handleBookmarkToggle,
  };
};
