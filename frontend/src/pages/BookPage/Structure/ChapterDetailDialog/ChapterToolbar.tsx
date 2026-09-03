import { useGenerateChapterDigest } from '@/api/generated/digest/digest';
import { AIActionButton } from '@/components/buttons/AIActionButton.tsx';
import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip.tsx';
import { ConfirmationDialog } from '@/components/dialogs/ConfirmationDialog.tsx';
import { DialogToolbar } from '@/components/dialogs/DialogToolbar.tsx';
import { AIFeature } from '@/components/features/AIFeature.tsx';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { AIIcon, LinkIcon, RegenerateIcon } from '@/theme/Icons.tsx';
import { copyUrlWithSearchParam } from '@/utils/clipboard.ts';
import { CircularProgress } from '@mui/material';
import { useState } from 'react';

interface ChapterToolbarProps {
  chapterId: number;
  bookId: number;
  hasSummary: boolean;
}

export const ChapterToolbar = ({ chapterId, bookId, hasSummary }: ChapterToolbarProps) => {
  const cache = useCacheEvents();
  const mutationErrorHandler = useMutationErrorHandler();
  const [confirmationOpen, setConfirmationOpen] = useState(false);

  const { mutate: generate, isPending } = useGenerateChapterDigest({
    mutation: {
      onError: mutationErrorHandler('generate summary'),
      onSuccess: () => {
        cache.digestChanged(bookId);
      },
    },
  });

  const handleGenerate = () => {
    if (hasSummary) {
      setConfirmationOpen(true);
      return;
    }
    generate({ chapterId });
  };

  const handleConfirmRegenerate = () => {
    setConfirmationOpen(false);
    generate({ chapterId });
  };

  const title = hasSummary ? 'Regenerate summary and questions' : 'Generate summary';
  const icon = hasSummary ? <RegenerateIcon /> : <AIIcon />;

  // A link that works from any context: `chapterId` is only a validated search
  // param on the structure route, so build the URL on that route.
  const handleCopyLink = async () => {
    await copyUrlWithSearchParam(
      'chapterId',
      chapterId,
      `${window.location.origin}/book/${bookId}/structure`
    );
  };

  // The toolbar itself is not an AI feature — only the generate button is, and
  // gating the whole row would take copy-link away with it.
  return (
    <>
      <DialogToolbar>
        <IconButtonWithTooltip
          label="Copy link to chapter"
          onClick={() => void handleCopyLink()}
          icon={<LinkIcon />}
        />
        <AIFeature>
          {isPending ? (
            <CircularProgress size={24} sx={{ m: '4px' }} />
          ) : (
            <AIActionButton text={title} onClick={handleGenerate} iconOnly icon={icon} />
          )}
        </AIFeature>
      </DialogToolbar>

      <ConfirmationDialog
        open={confirmationOpen}
        onClose={() => setConfirmationOpen(false)}
        onConfirm={handleConfirmRegenerate}
        confirmText="Regenerate"
        confirmColor="error"
        message="Regenerating this chapter replaces its summary, key points, and questions. Any saved answers to the current questions will be deleted."
      />
    </>
  );
};
