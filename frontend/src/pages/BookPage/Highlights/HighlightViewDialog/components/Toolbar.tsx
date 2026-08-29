import { useCreateBookmark, useDeleteBookmark } from '@/api/generated/bookmarks/bookmarks.ts';
import type { Bookmark } from '@/api/generated/model';
import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip.tsx';
import { DialogToolbar } from '@/components/dialogs/DialogToolbar.tsx';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
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
        label="Copy link to highlight"
        onClick={handleCopyLink}
        disabled={isDisabled}
        icon={<LinkIcon />}
      />
      <IconButtonWithTooltip
        label="Copy highlight content"
        onClick={handleCopyContent}
        disabled={isDisabled}
        icon={<CopyIcon />}
      />
      <IconButtonWithTooltip
        label={bookmark ? 'Remove bookmark' : 'Add bookmark'}
        onClick={handleBookmarkToggle}
        disabled={isDisabled}
        icon={bookmark ? <BookmarkFilledIcon /> : <BookmarkIcon />}
      />
      <IconButtonWithTooltip
        label="Delete highlight"
        onClick={onDelete}
        disabled={isDisabled}
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
  const mutationErrorHandler = useMutationErrorHandler();
  const cache = useCacheEvents();
  const [isProcessing, setIsProcessing] = useState(false);

  const createBookmarkMutation = useCreateBookmark({
    mutation: {
      onSuccess: () => cache.bookChanged(bookId),
      onError: mutationErrorHandler('create bookmark'),
    },
  });

  const deleteBookmarkMutation = useDeleteBookmark({
    mutation: {
      onSuccess: () => cache.bookChanged(bookId),
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
