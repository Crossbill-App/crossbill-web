"""Use case for embedding a single content unit (the task core)."""

from src.application.semantic.content_type import ContentType
from src.application.semantic.idempotency import current_model_name, is_current
from src.application.semantic.protocols.content_source import ContentSourceProtocol
from src.application.semantic.protocols.embedding_client import EmbeddingClientProtocol
from src.application.semantic.protocols.embedding_repository import (
    EmbeddingRepositoryProtocol,
    EmbeddingWrite,
)
from src.config import Settings


class GenerateContentEmbeddingUseCase:
    """Embeds one content unit, guarding every write with the idempotency spine.

    Missing source → delete the stale embedding. Unchanged hash and model →
    skip without a model call. Otherwise embed and upsert.
    """

    def __init__(
        self,
        content_source: ContentSourceProtocol,
        client: EmbeddingClientProtocol,
        repo: EmbeddingRepositoryProtocol,
        settings: Settings,
    ) -> None:
        self._content_source = content_source
        self._client = client
        self._repo = repo
        self._settings = settings

    async def execute(self, content_type: ContentType, content_id: int) -> None:
        emb = await self._content_source.get_embeddable(content_type, content_id)
        if emb is None:
            await self._repo.delete_for(content_type, content_id)
            return

        # Re-checking what the backfill already filtered on is deliberate: the
        # content can change between the two, and a model call is what is at
        # stake. The rule itself lives in one place so the two cannot disagree.
        state = await self._repo.get_state(content_type, content_id)
        if is_current(state, emb.content_hash, self._settings):
            return

        vectors = await self._client.embed([emb.text])
        await self._repo.upsert(
            EmbeddingWrite(
                content_type=emb.content_type,
                content_id=emb.content_id,
                user_id=emb.user_id,
                book_id=emb.book_id,
                embedding=vectors[0],
                model_name=current_model_name(self._settings),
                model_version=self._settings.EMBEDDING_MODEL_VERSION,
                content_hash=emb.content_hash,
            )
        )
