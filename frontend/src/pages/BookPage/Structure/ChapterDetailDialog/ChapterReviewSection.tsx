import type {
  ChapterDigestResponse,
  CollectionResponseChapterDigestResponse,
} from '@/api/generated/model';
import {
  getGetBookDigestQueryKey,
  useGenerateChapterDigest,
  useUpdateDigestAnswers,
} from '@/api/generated/digest/digest';
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
  digestSummary?: ChapterDigestResponse;
  onStartQuiz: () => void;
  onStartChat: () => void;
}

export const ChapterReviewSection = ({
  chapterId,
  bookId,
  digestSummary,
  onStartQuiz,
  onStartChat,
}: ChapterReviewSectionProps) => {
  const queryClient = useQueryClient();
  const cache = useCacheEvents();

  // Local edits keyed by chapterId so they reset when switching chapters
  const [localEdits, setLocalEdits] = useState<Record<number, Record<number, string>>>({});
  // Server answers derived from digestSummary
  const serverAnswers = useMemo<Record<number, string>>(() => {
    if (!digestSummary) return {};
    return Object.fromEntries(
      digestSummary.questions.map((q, index) => [index, q.user_answer])
    );
  }, [digestSummary]);

  // Merge server answers with local edits for the current chapter
  const answers: Record<number, string> = {
    ...serverAnswers,
    ...(localEdits[chapterId] ?? {}),
  };

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
          No digest questions available.
        </Typography>
      )}

      {!isPending && digestSummary && digestSummary.questions.length > 0 && (
        <CollapsibleSection title="Questions to think while reading" defaultExpanded>
          <Stack
            sx={{
              gap: 1,
            }}
          >
            {digestSummary.questions.map((q, index) => (
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
