import {
  getGetBookDigestQueryKey,
  useGenerateChapterDigest,
  useUpdateDigestAnswers,
} from '@/api/generated/digest/digest';
import type {
  ChapterDigestResponse,
  CollectionResponseChapterDigestResponse,
  DigestSearchItem,
} from '@/api/generated/model';
import { AIActionButton } from '@/components/buttons/AIActionButton.tsx';
import { AIFeature } from '@/components/features/AIFeature.tsx';
import { SavedIndicator } from '@/components/SavedIndicator.tsx';
import { digestRows } from '@/components/search/globalSearchRows.ts';
import { RelatedContentSection } from '@/components/search/RelatedContentSection.tsx';
import { useCommitOnBlur } from '@/hooks/useCommitOnBlur.ts';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useSaveStatus } from '@/hooks/useSaveStatus.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { Box, CircularProgress, Stack, TextField, Typography } from '@mui/material';
import { useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';
import { CollapsibleSection } from './CollapsibleSection.tsx';

interface SaveCallbacks {
  onSuccess: () => void;
  onError: () => void;
}

interface DigestAnswerFieldProps {
  question: string;
  savedAnswer: string;
  onSave: (answer: string, callbacks: SaveCallbacks) => void;
}

const DigestAnswerField = ({ question, savedAnswer, onSave }: DigestAnswerFieldProps) => {
  const saveStatus = useSaveStatus();

  function save(answer: string) {
    saveStatus.saving();
    onSave(answer, {
      onSuccess: saveStatus.saved,
      onError: () => {
        saveStatus.reset();
        field.allowRecommit();
      },
    });
  }

  const field = useCommitOnBlur({ saved: savedAnswer, onCommit: save, submitOnEnter: false });

  return (
    <Box sx={{ py: 1 }}>
      <Typography variant="body2" sx={{ fontWeight: 600, mb: 1.5 }}>
        {question}
      </Typography>
      <TextField
        multiline
        minRows={2}
        fullWidth
        size="small"
        placeholder="Write your answer..."
        {...field.inputProps}
      />
      <SavedIndicator status={saveStatus.status} sx={{ textAlign: 'right', mt: 0.5 }} />
    </Box>
  );
};

interface ChapterReviewSectionProps {
  chapterId: number;
  bookId: number;
  digestSummary?: ChapterDigestResponse;
  relatedContent: DigestSearchItem[];
  onStartQuiz: () => void;
  onStartChat: () => void;
}

export const ChapterReviewSection = ({
  chapterId,
  bookId,
  digestSummary,
  relatedContent,
  onStartQuiz,
  onStartChat,
}: ChapterReviewSectionProps) => {
  const queryClient = useQueryClient();
  const cache = useCacheEvents();
  const mutationErrorHandler = useMutationErrorHandler();

  const answers = useMemo<Record<number, string>>(() => {
    if (!digestSummary) return {};
    return Object.fromEntries(digestSummary.questions.map((q, index) => [index, q.user_answer]));
  }, [digestSummary]);

  const { mutate: generate, isPending } = useGenerateChapterDigest({
    mutation: {
      onSuccess: () => {
        cache.digestChanged(bookId);
      },
    },
  });

  const queryKey = getGetBookDigestQueryKey(bookId);

  const { mutate: saveAnswers } = useUpdateDigestAnswers({
    mutation: {
      onError: mutationErrorHandler('save answer'),
      onSuccess: (updatedChapter) => {
        queryClient.setQueryData<CollectionResponseChapterDigestResponse>(queryKey, (old) => {
          if (!old) return old;
          return {
            ...old,
            items: old.items.map((item) =>
              item.chapter_id === updatedChapter.chapter_id
                ? { ...item, questions: updatedChapter.questions }
                : item
            ),
          };
        });
      },
    },
  });

  const handleGenerate = () => {
    generate({ chapterId });
  };

  // The endpoint patches by question index, so one field's save leaves the
  // other answers as they are.
  const handleAnswerSave = (index: number, answer: string, callbacks: SaveCallbacks) => {
    saveAnswers(
      { chapterId, data: { answers: [{ question_index: index, user_answer: answer }] } },
      callbacks
    );
  };

  return (
    <>
      <AIFeature>
        {isPending && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
            <CircularProgress size={24} />
          </Box>
        )}

        {!isPending && !digestSummary && (
          <Box sx={{ py: 1 }}>
            <AIActionButton text="Generate questions" onClick={handleGenerate} />
          </Box>
        )}

        {!isPending && digestSummary && digestSummary.questions.length === 0 && (
          <Typography
            variant="body2"
            sx={{
              color: 'text.secondary',
            }}
          >
            No questions generated for this chapter.
          </Typography>
        )}

        {!isPending && digestSummary && digestSummary.questions.length > 0 && (
          <CollapsibleSection title="Questions to think about while reading" defaultExpanded>
            <Stack
              sx={{
                gap: 1,
              }}
            >
              {digestSummary.questions.map((q, index) => (
                <DigestAnswerField
                  // Keyed by chapter as well, so navigating chapters starts the
                  // fields fresh rather than carrying one chapter's text over.
                  key={`${chapterId}-${index}`}
                  question={q.question}
                  savedAnswer={answers[index] ?? ''}
                  onSave={(answer, callbacks) => handleAnswerSave(index, answer, callbacks)}
                />
              ))}
            </Stack>
          </CollapsibleSection>
        )}

        <Box sx={{ py: 1, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          <AIActionButton text="Quiz me" onClick={onStartQuiz} />
          <AIActionButton text="Chat about the chapter" onClick={onStartChat} />
        </Box>
      </AIFeature>

      {/* Outside `AIFeature`: related chapters come from the embedding index,
          which is a separate flag from the AI features above it. */}
      <RelatedContentSection title="Related chapters" rows={digestRows(relatedContent)} />
    </>
  );
};
