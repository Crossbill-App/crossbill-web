"""Shared log context extracted from the SAQ job."""

from typing import Any

from saq import Job
from saq.types import Context


def saq_job_context(ctx: Context) -> dict[str, Any]:
    """Log fields identifying the SAQ job and its retry state.

    ``attempt`` distinguishes one flaky job from many broken ones: repeated
    failure events with the same ``job_key`` and a rising ``attempt`` are a
    single job retrying.
    """
    job: Job | None = ctx.get("job")  # type: ignore[assignment]
    if job is None:
        return {}
    return {"job_key": job.key, "attempt": job.attempts, "retries": job.retries}
