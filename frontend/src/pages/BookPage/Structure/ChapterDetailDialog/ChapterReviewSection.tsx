import type {
  ChapterPrereadingResponse,
  CollectionResponseChapterPrereadingResponse,
} from '@/api/generated/model';
import {
  getGetBookPrereadingQueryKey,
  useGenerateChapterPrereading,
  useUpdatePrereadingAnswers,
} from '@/api/generated/prereading/prereading';
import { AIActionButton } from '@/components/buttons/AIActionButton.tsx';
import { AIFeature } from '@/components/features/AIFeature.tsx';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { Box, CircularProgress, Stack, TextField, Typography } from '@mui/material';
import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useMemo, useState } from 'react';
import { CollapsibleSection } from './CollapsibleSection.tsx';

interface ChapterReviewSectionProps {
  chapterId: number;
  bookId: number;
  prereadingSummary?: ChapterPrereadingResponse;
  onStartQuiz: () => void;
  onStartChat: () => void;
}

export const ChapterReviewSection = ({
  chapterId,
  bookId,
  prereadingSummary,
  onStartQuiz,
  onStartChat,
}: ChapterReviewSectionProps) => {
  const queryClient = useQueryClient();
  const cache = useCacheEvents();

  // Local edits keyed by chapterId so they reset when switching chapters
  const [localEdits, setLocalEdits] = useState<Record<number, Record<number, string>>>({});
  // Server answers derived from prereadingSummary
  const serverAnswers = useMemo<Record<number, string>>(() => {
    if (!prereadingSummary) return {};
    return Object.fromEntries(
      prereadingSummary.questions.map((q, index) => [index, q.user_answer])
    );
  }, [prereadingSummary]);

  // Merge server answers with local edits for the current chapter
  const answers: Record<number, string> = {
    ...serverAnswers,
    ...(localEdits[chapterId] ?? {}),
  };

  const { mutate: generate, isPending } = useGenerateChapterPrereading({
    mutation: {
      onSuccess: () => {
        cache.prereadingChanged(bookId);
      },
    },
  });

  const queryKey = getGetBookPrereadingQueryKey(bookId);

  const { mutate: saveAnswers } = useUpdatePrereadingAnswers({
    mutation: {
      onSuccess: (updatedChapter) => {
        queryClient.setQueryData<CollectionResponseChapterPrereadingResponse>(queryKey, (old) => {
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
        setLocalEdits((prev) =>
          Object.fromEntries(Object.entries(prev).filter(([key]) => Number(key) !== chapterId))
        );
      },
    },
  });

  const saveNow = useCallback(
    (answersToSave: Record<number, string>) => {
      const answerList = Object.entries(answersToSave).map(([index, answer]) => ({
        question_index: Number(index),
        user_answer: answer,
      }));
      saveAnswers({ chapterId, data: { answers: answerList } });
    },
    [chapterId, saveAnswers]
  );

  const handleGenerate = () => {
    generate({ chapterId });
  };

  const handleAnswerChange = (index: number, value: string) => {
    setLocalEdits((prev) => ({
      ...prev,
      [chapterId]: { ...(prev[chapterId] ?? {}), [index]: value },
    }));
  };

  const handleBlur = () => {
    saveNow(answers);
  };

  return (
    <AIFeature>
      {isPending && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
          <CircularProgress size={24} />
        </Box>
      )}

      {!isPending && !prereadingSummary && (
        <Box sx={{ py: 1 }}>
          <AIActionButton text="Generate questions" onClick={handleGenerate} />
        </Box>
      )}

      {!isPending && prereadingSummary && prereadingSummary.questions.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          No pre-reading questions available.
        </Typography>
      )}

      {!isPending && prereadingSummary && prereadingSummary.questions.length > 0 && (
        <CollapsibleSection title="Questions to think while reading" defaultExpanded>
          <Stack gap={1}>
            {prereadingSummary.questions.map((q, index) => (
              <Box key={index} sx={{ py: 1 }}>
                <Typography variant="body2" sx={{ fontWeight: 600, mb: 1.5 }}>
                  {q.question}
                </Typography>
                <TextField
                  multiline
                  minRows={2}
                  fullWidth
                  size="small"
                  placeholder="Write your answer..."
                  value={answers[index] ?? ''}
                  onChange={(e) => handleAnswerChange(index, e.target.value)}
                  onBlur={handleBlur}
                />
              </Box>
            ))}
          </Stack>
        </CollapsibleSection>
      )}

      <Box sx={{ py: 1, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        <AIActionButton text="Quiz me" onClick={onStartQuiz} />
        <AIActionButton text="Chat about the chapter" onClick={onStartChat} />
      </Box>
    </AIFeature>
  );
};
