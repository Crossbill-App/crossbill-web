import type { JobBatchResponse } from '@/api/generated/model';
import { http, HttpResponse } from 'msw';
import { aJobBatch } from '../fixtures/jobs';

const TERMINAL_STATUSES = ['completed', 'completed_with_errors', 'failed', 'cancelled'];

interface SemanticApiState {
  /** Jobs the next backfill request enqueues. 0 means everything is indexed. */
  pendingJobs: number;
  batch: JobBatchResponse | null;
}

/**
 * The semantic backfill endpoints plus the job-batch endpoints they hand off
 * to, backed by mutable state so a POST is visible to the polling GET that
 * follows it.
 *
 * `advance` stands in for the worker: a test calls it to move the running batch
 * on, and the next poll sees the new counts the way the real page would.
 */
export function semanticApi(initial: Partial<SemanticApiState> = {}) {
  const state: SemanticApiState = {
    pendingJobs: initial.pendingJobs ?? 4,
    batch: initial.batch ?? null,
  };

  const running = () =>
    state.batch && !TERMINAL_STATUSES.includes(state.batch.status) ? state.batch : null;

  const advance = (patch: Partial<JobBatchResponse>) => {
    if (state.batch) {
      state.batch = { ...state.batch, ...patch };
    }
  };

  const handlers = [
    http.get('/api/v1/semantic/backfill/active', () => HttpResponse.json(running())),

    http.post('/api/v1/semantic/backfill', () => {
      if (running()) {
        return new HttpResponse(null, { status: 409 });
      }
      if (state.pendingJobs === 0) {
        return HttpResponse.json({ total_jobs: 0, batch: null });
      }
      state.batch = aJobBatch({ total_jobs: state.pendingJobs });
      return HttpResponse.json(
        { total_jobs: state.pendingJobs, batch: state.batch },
        { status: 202 }
      );
    }),

    http.get('/api/v1/jobs/batches/:batchId', () =>
      state.batch ? HttpResponse.json(state.batch) : new HttpResponse(null, { status: 404 })
    ),

    http.delete('/api/v1/jobs/batches/:batchId', () => {
      advance({ status: 'cancelled' });
      return HttpResponse.json(state.batch);
    }),
  ];

  return { handlers, state, advance };
}
