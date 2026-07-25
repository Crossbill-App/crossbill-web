import {
  getGetBookPrereadingQueryKey,
  useGenerateChapterPrereading,
} from '@/api/generated/prereading/prereading';
import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip.tsx';
import { DialogToolbar } from '@/components/dialogs/DialogToolbar.tsx';
import { AIFeature } from '@/components/features/AIFeature.tsx';
import { AIIcon, RegenerateIcon } from '@/theme/Icons.tsx';
import { CircularProgress } from '@mui/material';
import { useQueryClient } from '@tanstack/react-query';

interface ChapterToolbarProps {
  chapterId: number;
  bookId: number;
  hasSummary: boolean;
}

export const ChapterToolbar = ({ chapterId, bookId, hasSummary }: ChapterToolbarProps) => {
  const queryClient = useQueryClient();

  const { mutate: generate, isPending } = useGenerateChapterPrereading({
    mutation: {
      onSuccess: () => {
        void queryClient.invalidateQueries({
          queryKey: getGetBookPrereadingQueryKey(bookId),
        });
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
          <IconButtonWithTooltip
            title={title}
            onClick={handleGenerate}
            ariaLabel={title}
            icon={icon}
          />
        )}
      </DialogToolbar>
    </AIFeature>
  );
};
