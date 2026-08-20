"""Volatile in-memory signals for dashboards (not durable — internal token only)."""

from __future__ import annotations

import itertools
import time
from collections import OrderedDict, deque
from typing import Any


class AlertRing:
    """Critical alerts polled by `/internal/alerts` for toaster UX."""

    def __init__(self, maxlen: int = 256) -> None:
        self._items: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._counter = itertools.count(1)

    def push_critical(
        self, *, headline: str, detail: str, correlation_id: str, source: str
    ) -> str:
        aid = str(next(self._counter))
        evt = {
            "id": aid,
            "ts": time.time(),
            "severity": "critical",
            "headline": headline,
            "detail": detail,
            "correlation_id": correlation_id,
            "source": source,
        }
        self._items.append(evt)
        return aid

    def pull_since(self, since_ts: float) -> list[dict[str, Any]]:
        return [e for e in self._items if e["ts"] > since_ts]


class PromptDebugBuffer:
    """Original vs outbound scrub snapshots (TTL + ring). Never written to SQLite."""

    def __init__(self, max_entries: int = 96, ttl_seconds: float = 900.0) -> None:
        self._max = max_entries
        self._ttl = ttl_seconds
        self._data: OrderedDict[str, tuple[float, str, str]] = OrderedDict()

    def _prune(self) -> None:
        now = time.time()
        for cid, (stamp, _, _) in list(self._data.items()):
            if now - stamp > self._ttl:
                del self._data[cid]

    def put(self, corr_id: str, original: str, scrubbed: str) -> None:
        self._prune()
        while len(self._data) >= self._max:
            oldest = next(iter(self._data))
            del self._data[oldest]
        self._data[corr_id] = (time.time(), original, scrubbed)

    def get(self, corr_id: str) -> dict[str, str] | None:
        self._prune()
        row = self._data.get(corr_id)
        if not row:
            return None
        _, original, scrubbed = row
        return {"original_prompt": original, "scrubbed_prompt": scrubbed}
