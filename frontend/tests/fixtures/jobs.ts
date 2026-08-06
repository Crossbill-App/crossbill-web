import type { JobBatchResponse } from '@/api/generated/model';

export const aJobBatch = (overrides: Partial<JobBatchResponse> = {}): JobBatchResponse => ({
  id: 7,
  batch_type: 'content_embedding_backfill',
  reference_id: '1',
  total_jobs: 4,
  completed_jobs: 0,
  failed_jobs: 0,
  status: 'processing',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  ...overrides,
});
