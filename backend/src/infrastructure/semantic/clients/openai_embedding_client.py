"""OpenAI-compatible embedding client (Ollama / OpenRouter by base URL)."""

import httpx

from src.application.semantic.protocols.embedding_client import EmbeddingClientProtocol
from src.config import Settings
from src.infrastructure.semantic.dimensions import EMBEDDING_DIMENSIONS

# OpenRouter caps a single /embeddings request at 96 inputs; chunk to stay under it.
_MAX_INPUTS_PER_REQUEST = 96
_DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_REQUEST_TIMEOUT_SECONDS = 60.0


class EmbeddingClientError(RuntimeError):
    """Raised when the embeddings endpoint returns an unusable response."""


class OpenAIEmbeddingClient(EmbeddingClientProtocol):
    """Calls an OpenAI-compatible ``/embeddings`` endpoint over HTTP.

    Ollama and OpenRouter both expose this shape, so the provider is only a base
    URL plus an optional bearer key — nothing branches on provider here.
    """

    def __init__(
        self,
        *,
        base_url: str,
        model_name: str,
        dimensions: int,
        api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._dimensions = dimensions
        self._api_key = api_key
        self._transport = transport

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed each text, preserving input order and validating dimensions."""
        if not texts:
            return []

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        vectors: list[list[float]] = []
        async with httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT_SECONDS, transport=self._transport
        ) as client:
            for start in range(0, len(texts), _MAX_INPUTS_PER_REQUEST):
                chunk = texts[start : start + _MAX_INPUTS_PER_REQUEST]
                response = await client.post(
                    f"{self._base_url}/embeddings",
                    headers=headers,
                    json={"model": self._model_name, "input": chunk},
                )
                response.raise_for_status()
                vectors.extend(self._parse(response.json(), expected=len(chunk)))
        return vectors

    def _parse(self, payload: object, *, expected: int) -> list[list[float]]:
        if not isinstance(payload, dict):
            msg = "embeddings response was not a JSON object"
            raise EmbeddingClientError(msg)
        data = payload.get("data")
        if not isinstance(data, list) or len(data) != expected:
            msg = f"embeddings response returned {_count(data)} vectors, expected {expected}"
            raise EmbeddingClientError(msg)

        vectors: list[list[float]] = []
        for item in sorted(data, key=_index_of):
            embedding = item.get("embedding") if isinstance(item, dict) else None
            if not isinstance(embedding, list):
                msg = "embeddings response item was missing an 'embedding' list"
                raise EmbeddingClientError(msg)
            if len(embedding) != self._dimensions:
                msg = f"embedding had {len(embedding)} dimensions, expected {self._dimensions}"
                raise EmbeddingClientError(msg)
            vectors.append([float(value) for value in embedding])
        return vectors


def _index_of(item: object) -> int:
    index = item.get("index") if isinstance(item, dict) else None
    return index if isinstance(index, int) else 0


def _count(data: object) -> int:
    return len(data) if isinstance(data, list) else 0


def build_embedding_client(settings: Settings) -> EmbeddingClientProtocol:
    """Build the embedding client from settings, resolving base URL and key by provider.

    Reused by the DI container and the background worker, so it stays purely
    settings-driven. Assumes ``validate_embedding_provider_config`` has passed.
    """
    provider = settings.EMBEDDING_PROVIDER
    if provider is None:
        msg = "EMBEDDING_PROVIDER is not configured"
        raise EmbeddingClientError(msg)
    if settings.EMBEDDING_MODEL_NAME is None:
        msg = "EMBEDDING_MODEL_NAME is not configured"
        raise EmbeddingClientError(msg)

    if provider == "ollama":
        if not settings.EMBEDDING_BASE_URL:
            msg = "EMBEDDING_BASE_URL is required for the ollama provider"
            raise EmbeddingClientError(msg)
        base_url = settings.EMBEDDING_BASE_URL
        api_key = None
    else:  # openrouter
        base_url = settings.EMBEDDING_BASE_URL or _DEFAULT_OPENROUTER_BASE_URL
        api_key = settings.OPENROUTER_API_KEY

    return OpenAIEmbeddingClient(
        base_url=base_url,
        model_name=settings.EMBEDDING_MODEL_NAME,
        dimensions=EMBEDDING_DIMENSIONS,
        api_key=api_key,
    )
