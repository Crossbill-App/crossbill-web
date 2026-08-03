"""Port for the embedding model client."""

from typing import Protocol


class EmbeddingClientProtocol(Protocol):
    """Turns text into dense vectors via an OpenAI-compatible embeddings API."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed each input text, returning vectors in the same order."""
        ...
