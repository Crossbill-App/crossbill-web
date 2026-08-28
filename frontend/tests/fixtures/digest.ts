import type { ChapterDigestResponse, DigestQuestionResponse } from '@/api/generated/model';

export const aDigestQuestion = (
  overrides: Partial<DigestQuestionResponse> = {}
): DigestQuestionResponse => ({
  question: 'What makes attention a filter?',
  answer: 'It selects what reaches working memory.',
  user_answer: '',
  ...overrides,
});

export const aChapterDigest = (
  overrides: Partial<ChapterDigestResponse> = {}
): ChapterDigestResponse => ({
  id: 500,
  chapter_id: 10,
  summary: 'Attention decides what is remembered.',
  keypoints: ['Attention is selective'],
  questions: [aDigestQuestion()],
  generated_at: '2026-01-01T00:00:00Z',
  ...overrides,
});
