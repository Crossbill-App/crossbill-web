"""An embedding client that defers construction until something actually embeds.

``build_embedding_client`` raises when no provider is configured, which is the
right behaviour on its own — a misconfigured worker should fail loudly. But the
DI container resolves the client while FastAPI is assembling an endpoint's
parameter dependencies, which happens *before* the body of a
``require_embeddings_enabled`` decorator runs. Building eagerly there turns a
disabled feature into a 500 that the feature gate never gets a chance to answer.

``src.infrastructure.ai.ai_model`` has the same raising behaviour (``_get_model``
raises when no provider matches) and avoids the problem the same way: its
``get_ai_model`` is only called from inside the handler. This wrapper gives the
embedding client that laziness without asking every caller to remember it, so
the feature gate can stay a decorator like ``require_ai_enabled`` rather than
becoming a second pattern.
"""

from src.application.semantic.protocols.embedding_client import EmbeddingClientProtocol
from src.config import Settings
from src.infrastructure.semantic.clients.openai_embedding_client import build_embedding_client


class LazyEmbeddingClient(EmbeddingClientProtocol):
    """Builds the configured client on first ``embed``, then reuses it."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: EmbeddingClientProtocol | None = None

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if self._client is None:
            self._client = build_embedding_client(self._settings)
        return await self._client.embed(texts)
