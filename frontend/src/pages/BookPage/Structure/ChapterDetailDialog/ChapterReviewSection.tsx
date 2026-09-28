import {
  getGetBookDigestQueryKey,
  useGenerateChapterDigest,
  useUpdateDigestAnswers,
} from '@/api/generated/digest/digest';
import type {
  ChapterDigestResponse,
  CollectionResponseChapterDigestResponse,
} from '@/api/generated/model';
import { AIActionButton } from '@/components/buttons/AIActionButton.tsx';
import { AIFeature } from '@/components/features/AIFeature.tsx';
import { SavedIndicator } from '@/components/SavedIndicator.tsx';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { useCommitOnBlur } from '@/hooks/useCommitOnBlur.ts';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useSaveStatus } from '@/hooks/useSaveStatus.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { Box, CircularProgress, Stack, TextField, Typography } from '@mui/material';
import { useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

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
  const { t } = useTranslation();
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
        placeholder={t('structure.chapterDetail.review.answerPlaceholder')}
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
}

export const ChapterReviewSection = ({
  chapterId,
  bookId,
  digestSummary,
}: ChapterReviewSectionProps) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const cache = useCacheEvents();
  const mutationErrorHandler = useMutationErrorHandler();

  const answers = useMemo<Record<number, string>>(() => {
    if (!digestSummary) return {};
    return Object.fromEntries(digestSummary.questions.map((q, index) => [index, q.user_answer]));
  }, [digestSummary]);

  const { mutate: generate, isPending } = useGenerateChapterDigest({
    mutation: {
      onError: mutationErrorHandler(t('structure.chapterDetail.review.errors.generateQuestions')),
      onSuccess: () => {
        cache.digestChanged(bookId);
      },
    },
  });

  const queryKey = getGetBookDigestQueryKey(bookId);

  const { mutate: saveAnswers } = useUpdateDigestAnswers({
    mutation: {
      onError: mutationErrorHandler(t('structure.chapterDetail.review.errors.saveAnswer')),
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
            <AIActionButton
              text={t('structure.chapterDetail.review.generateQuestions')}
              onClick={handleGenerate}
            />
          </Box>
        )}

        {!isPending && digestSummary && digestSummary.questions.length === 0 && (
          <Typography
            variant="body2"
            sx={{
              color: 'text.secondary',
            }}
          >
            {t('structure.chapterDetail.review.noQuestions')}
          </Typography>
        )}

        {!isPending && digestSummary && digestSummary.questions.length > 0 && (
          <Box>
            <SectionTitle component="h3">
              {t('structure.chapterDetail.review.questionsTitle')}
            </SectionTitle>
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
          </Box>
        )}
      </AIFeature>
    </>
  );
};
