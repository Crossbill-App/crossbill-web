import { useGenerateChapterDigest } from '@/api/generated/digest/digest';
import { AIActionButton } from '@/components/buttons/AIActionButton.tsx';
import { DialogToolbar } from '@/components/dialogs/DialogToolbar.tsx';
import { AIFeature } from '@/components/features/AIFeature.tsx';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { AIIcon, RegenerateIcon } from '@/theme/Icons.tsx';
import { CircularProgress } from '@mui/material';

interface ChapterToolbarProps {
  chapterId: number;
  bookId: number;
  hasSummary: boolean;
}

export const ChapterToolbar = ({ chapterId, bookId, hasSummary }: ChapterToolbarProps) => {
  const cache = useCacheEvents();

  const { mutate: generate, isPending } = useGenerateChapterDigest({
    mutation: {
      onSuccess: () => {
        cache.digestChanged(bookId);
      },
    },
  });

  const handleGenerate = () => {
    generate({ chapterId });
  };

  const title = hasSummary ? 'Regenerate summary and questions' : 'Generate summary';
  const icon = hasSummary ? <RegenerateIcon /> : <AIIcon />;

  return (
    <AIFeature>
      <DialogToolbar>
        {isPending ? (
          <CircularProgress size={24} sx={{ m: '4px' }} />
        ) : (
          <AIActionButton text={title} onClick={handleGenerate} iconOnly icon={icon} />
        )}
      </DialogToolbar>
    </AIFeature>
  );
};
