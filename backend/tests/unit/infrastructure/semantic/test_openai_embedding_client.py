"""Unit tests for the OpenAI-compatible embedding client."""

import json

import httpx
import pytest

from src.infrastructure.semantic.clients.openai_embedding_client import (
    EmbeddingClientError,
    OpenAIEmbeddingClient,
)

DIMENSIONS = 4


def _vector(seed: int) -> list[float]:
    return [float(seed)] * DIMENSIONS


class _Recorder:
    """Captures requests and replies with dimension-correct embeddings."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)

        inputs = json.loads(request.content)["input"]
        # Return items out of order to prove the client re-sorts by index.
        data = [{"index": i, "embedding": _vector(i)} for i in range(len(inputs))]
        return httpx.Response(200, json={"data": list(reversed(data))})


def _client(recorder: _Recorder, *, api_key: str | None = None) -> OpenAIEmbeddingClient:
    return OpenAIEmbeddingClient(
        base_url="http://embeddings.test/v1",
        model_name="bge-m3",
        dimensions=DIMENSIONS,
        api_key=api_key,
        transport=httpx.MockTransport(recorder.handler),
    )


class TestEmbedRequestShape:
    async def test_posts_model_and_input_to_embeddings_path(self) -> None:
        recorder = _Recorder()
        await _client(recorder).embed(["hello", "world"])

        request = recorder.requests[0]
        assert request.url.path == "/v1/embeddings"

        body = json.loads(request.content)
        assert body["model"] == "bge-m3"
        assert body["input"] == ["hello", "world"]

    async def test_sends_bearer_header_only_when_key_is_set(self) -> None:
        with_key = _Recorder()
        await _client(with_key, api_key="secret").embed(["x"])
        assert with_key.requests[0].headers["Authorization"] == "Bearer secret"

        without_key = _Recorder()
        await _client(without_key).embed(["x"])
        assert "Authorization" not in without_key.requests[0].headers


class TestEmbedChunking:
    async def test_chunks_inputs_at_96_per_request(self) -> None:
        """Pins the provider-cap guarantee, which no caller currently reaches.

        Callers batch well under 96, so this is the only thing holding the split
        in place -- and the only warning if a caller ever starts passing more.
        """
        recorder = _Recorder()
        vectors = await _client(recorder).embed([f"t{i}" for i in range(200)])

        assert len(recorder.requests) == 3

        sizes = [len(json.loads(r.content)["input"]) for r in recorder.requests]
        assert sizes == [96, 96, 8]
        assert len(vectors) == 200


class TestEmbedOrdering:
    async def test_preserves_input_order_despite_shuffled_response(self) -> None:
        recorder = _Recorder()
        vectors = await _client(recorder).embed(["a", "b", "c"])

        assert vectors == [_vector(0), _vector(1), _vector(2)]


class TestEmbedValidation:
    async def test_rejects_vector_with_wrong_dimensions(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0, 2.0]}]})

        client = OpenAIEmbeddingClient(
            base_url="http://embeddings.test/v1",
            model_name="bge-m3",
            dimensions=DIMENSIONS,
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(EmbeddingClientError, match="dimensions"):
            await client.embed(["oops"])

    async def test_rejects_response_with_missing_vectors(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"data": []})

        client = OpenAIEmbeddingClient(
            base_url="http://embeddings.test/v1",
            model_name="bge-m3",
            dimensions=DIMENSIONS,
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(EmbeddingClientError, match="expected"):
            await client.embed(["a", "b"])

    async def test_empty_input_makes_no_request(self) -> None:
        recorder = _Recorder()
        vectors = await _client(recorder).embed([])
        assert vectors == []
        assert recorder.requests == []
