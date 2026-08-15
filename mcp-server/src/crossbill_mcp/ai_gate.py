"""Shared handling for endpoints gated behind an AI provider."""

import json
from collections.abc import Awaitable
from typing import Any

import httpx

AI_DISABLED_MESSAGE = (
    "AI features are not enabled on this Crossbill server "
    "(no AI provider configured)."
)


async def ai_gated_json(call: Awaitable[Any]) -> str:
    """Await an AI-gated client call and return its result as JSON.

    Answers with AI_DISABLED_MESSAGE when the server reports HTTP 410, which
    is how it says no AI provider is configured.
    """
    try:
        result = await call
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 410:
            return AI_DISABLED_MESSAGE
        raise
    return json.dumps(result, indent=2, default=str)
