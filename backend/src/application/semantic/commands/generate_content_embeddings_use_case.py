"""Use case for embedding a slice of content units (the task core)."""

from src.application.semantic.content_type import ContentType
from src.application.semantic.idempotency import current_model_name, is_current
from src.application.semantic.protocols.content_source import ContentSourceProtocol
from src.application.semantic.protocols.embedding_client import EmbeddingClientProtocol
from src.application.semantic.protocols.embedding_repository import (
    EmbeddingRepositoryProtocol,
    EmbeddingWrite,
)
from src.config import Settings


class GenerateContentEmbeddingsUseCase:
    """Embeds a slice of content units of one type, guarding every write with the spine.

    Missing sources → delete the embeddings they left behind. Unchanged hash and
    model → skipped without a model call. Whatever is left is embedded in one
    request and written in one statement, which is the whole point of the slice:
    a job per unit meant a provider round trip per unit.
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

    async def execute(self, content_type: ContentType, content_ids: list[int]) -> None:
        if not content_ids:
            return

        resolved = await self._content_source.get_embeddable_many(content_type, content_ids)

        # Ids that resolved to nothing have lost their source row or had it
        # soft-deleted, so the embedding left behind is exactly what the
        # backfill's orphan sweep handed this slice to prune.
        missing = [content_id for content_id in content_ids if content_id not in resolved]
        await self._repo.delete_for(content_type, missing)

        # Re-checking what the backfill already filtered on is deliberate: the
        # content can change between the two, and a slice of model calls is what
        # is at stake. The rule itself lives in one place so the two cannot
        # disagree.
        states = await self._repo.get_states(content_type, list(resolved))
        pending = [
            content
            for content_id, content in resolved.items()
            if not is_current(states.get(content_id), content.content_hash, self._settings)
        ]
        if not pending:
            return

        # TODO: a slice fails as a unit, so one unit that cannot be embedded --
        # text the provider rejects, most likely for length -- takes the rest of
        # its slice down with it, on every retry and on every later backfill.
        # The fix is to fall back to embedding one unit at a time on the error
        # path, so only the genuine offender fails. Deliberately not done yet: it
        # buys nothing until such a unit exists, and the task handler logs the
        # slice's ids on failure, so identifying one costs a log search rather
        # than a code change.
        vectors = await self._client.embed([content.text for content in pending])
        await self._repo.upsert_many(
            [
                EmbeddingWrite(
                    content_type=content.content_type,
                    content_id=content.content_id,
                    user_id=content.user_id,
                    book_id=content.book_id,
                    embedding=vector,
                    model_name=current_model_name(self._settings),
                    model_version=self._settings.EMBEDDING_MODEL_VERSION,
                    content_hash=content.content_hash,
                )
                # strict: the client already validates that it got one vector per
                # input, so a mismatch here would mean it lied rather than that a
                # tail should be dropped.
                for content, vector in zip(pending, vectors, strict=True)
            ]
        )
