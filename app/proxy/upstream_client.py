"""HTTP helpers for any OpenAI-compatible upstream (Bearer token + chat completions path)."""

from __future__ import annotations

from typing import Any

import httpx


def chat_completions_endpoint(base_url: str) -> str:
    """
    Join base URL with the chat-completions path without duplicating ``/v1``.

    - ``https://api.openai.com`` → ``.../v1/chat/completions``
    - ``https://api.openai.com/v1`` → ``.../v1/chat/completions``
    - ``https://api.groq.com/openai/v1`` → ``.../openai/v1/chat/completions``
    """
    b = base_url.rstrip("/")
    if b.endswith("/v1"):
        return f"{b}/chat/completions"
    return f"{b}/v1/chat/completions"


async def post_chat_completion(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    payload: dict[str, Any],
) -> httpx.Response:
    url = chat_completions_endpoint(base_url)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return await client.post(url, json=payload, headers=headers)
