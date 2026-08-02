---
name: background-jobs
description: How the SAQ background worker is wired and how to add a new job type. Use when adding, changing, or debugging a background job, JobBatch, or worker task handler.
---

# Background Worker (SAQ)

The backend runs a background job queue on [SAQ](https://github.com/tobymao/saq) with
PostgreSQL as the queue backend (no Redis required). The worker is a separate process
using the same Docker image with a different entrypoint (`saq src.worker.worker_settings`).

## How It Works

- **Job Queue**: SAQ manages job enqueueing, dequeuing (via Postgres LISTEN/NOTIFY), retries, and cancellation. SAQ creates its own tables (`saq_jobs`, `saq_stats`, `saq_versions`) automatically.
- **JobBatch**: A domain entity (`src/domain/jobs/entities/job_batch.py`) tracks groups of related SAQ jobs. For example, generating digests for all chapters of a book creates one `JobBatch` with N individual SAQ jobs.
- **Worker Process**: Creates a fresh DB session per task to avoid sharing sessions across concurrent coroutines.
- **Task Handlers**: Task logic lives in `src/infrastructure/jobs/tasks/`. Each handler class receives dependencies via constructor injection. The worker builds these handlers with fresh sessions per invocation.
- **Batch Progress**: Uses atomic SQL increments (not read-modify-write) to safely update batch progress from concurrent tasks.
- **Concurrency**: Controlled via `WORKER_CONCURRENCY` env var (default: 5).

## Adding New Job Types

1. Add a new value to `JobBatchType` enum in `src/domain/jobs/entities/job_batch.py`
2. Create a task handler in `src/infrastructure/jobs/tasks/`
3. Create a top-level async task function in `src/worker.py` and register it in `worker_settings["functions"]`
4. Create an enqueue use case in `src/application/jobs/commands/`
5. Wire it through the DI container (`src/containers/jobs.py`)

The chapter digest generator is the reference implementation of a batch-producing
job: `src/infrastructure/jobs/tasks/digest_task_handler.py`, with
`job_lifecycle_handler.py` alongside it for the batch bookkeeping.
