"""When a stored embedding is still current -- ADR-0002's idempotency spine.

Two places ask this question, and they must answer it identically: the backfill
filters candidates with it, and the job re-checks it before spending a model
call (that pair is a deliberate TOCTOU guard, not duplication). The *rule*,
however, lives here only. It was written out twice before, each copy carrying a
comment asking the reader to keep it in step with the other, and they drifted
anyway -- an embedding stored with ``model_name or ""`` compared against a raw
``None`` read every row as permanently stale.
"""

from src.application.semantic.protocols.embedding_repository import EmbeddingState
from src.config import Settings


def current_model_name(settings: Settings) -> str:
    """The model name to both store and compare against.

    Coerced in one place because comparing and storing must use the identical
    value: an unset EMBEDDING_MODEL_NAME stored as ``""`` never equals ``None``.
    """
    return settings.EMBEDDING_MODEL_NAME or ""


def is_current(state: EmbeddingState | None, content_hash: str, settings: Settings) -> bool:
    """Whether a stored embedding still stands for this content and model.

    ``None`` means nothing is stored yet, which is never current.
    """
    if state is None:
        return False
    return (
        state.content_hash == content_hash
        and state.model_name == current_model_name(settings)
        and state.model_version == settings.EMBEDDING_MODEL_VERSION
    )
