"""Token budget and simple RPM guard per Shield API key."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field

import tiktoken
from fastapi import HTTPException

from app.core.settings import Settings


@dataclass
class _KeyState:
    tokens_used: int = 0
    minute_hits: deque[float] = field(default_factory=lambda: deque(maxlen=500))


class RateLimitChecker:
    _lock = asyncio.Lock()
    _by_key: dict[str, _KeyState] = {}

    @classmethod
    async def assert_within_budget(
        cls,
        shield_key: str | None,
        payload_text: str,
        settings: Settings,
    ) -> None:
        key = shield_key or "anonymous"
        enc = tiktoken.get_encoding("cl100k_base")
        est = len(enc.encode(payload_text))
        now = time.monotonic()
        window = 60.0
        async with cls._lock:
            st = cls._by_key.setdefault(key, _KeyState())
            while st.minute_hits and now - st.minute_hits[0] > window:
                st.minute_hits.popleft()
            if len(st.minute_hits) >= settings.rate_limit_rpm:
                raise HTTPException(status_code=429, detail="Rate limit exceeded (RPM)")
            if st.tokens_used + est > settings.token_budget_per_key:
                raise HTTPException(status_code=429, detail="Token budget exceeded")
            st.tokens_used += est
            st.minute_hits.append(now)

    @classmethod
    async def account_response_tokens(cls, shield_key: str | None, text: str) -> None:
        key = shield_key or "anonymous"
        enc = tiktoken.get_encoding("cl100k_base")
        est = len(enc.encode(text))
        async with cls._lock:
            st = cls._by_key.setdefault(key, _KeyState())
            st.tokens_used += est
