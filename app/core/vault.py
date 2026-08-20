from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.core.encryption import build_cipher


@dataclass
class VaultEntry:
    original: str
    entity_type: str
    expires_at: float


@runtime_checkable
class PiiVault(Protocol):
    async def put(self, vault_key: str, token: str, original: str, entity_type: str) -> None: ...
    async def get(self, vault_key: str, token: str) -> str | None: ...
    async def clear_key(self, vault_key: str) -> None: ...


class DictVault:
    """Async-safe in-process vault with TTL and bounded size per request key."""

    def __init__(
        self,
        ttl_seconds: float,
        max_entries_per_key: int = 10_000,
        encryption_key: str | None = None,
    ) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries_per_key
        self._lock = asyncio.Lock()
        self._data: dict[str, OrderedDict[str, VaultEntry]] = {}
        self._cipher = build_cipher(encryption_key)

    @property
    def encryption_enabled(self) -> bool:
        return bool(getattr(self._cipher, "enabled", False))

    def _now(self) -> float:
        return time.monotonic()

    async def put(
        self, vault_key: str, token: str, original: str, entity_type: str
    ) -> None:
        async with self._lock:
            bucket = self._data.setdefault(vault_key, OrderedDict())
            bucket[token] = VaultEntry(
                original=self._cipher.encrypt(original),
                entity_type=entity_type,
                expires_at=self._now() + self._ttl,
            )
            bucket.move_to_end(token)
            while len(bucket) > self._max:
                bucket.popitem(last=False)

    async def get(self, vault_key: str, token: str) -> str | None:
        async with self._lock:
            bucket = self._data.get(vault_key)
            if not bucket:
                return None
            entry = bucket.get(token)
            if entry is None:
                return None
            if entry.expires_at < self._now():
                del bucket[token]
                return None
            return self._cipher.decrypt(entry.original)

    async def clear_key(self, vault_key: str) -> None:
        async with self._lock:
            self._data.pop(vault_key, None)

    async def mapping_count(self, vault_key: str) -> int:
        async with self._lock:
            bucket = self._data.get(vault_key)
            return len(bucket) if bucket else 0

    async def prune_expired(self) -> None:
        now = self._now()
        async with self._lock:
            for vk, bucket in list(self._data.items()):
                dead = [t for t, e in bucket.items() if e.expires_at < now]
                for t in dead:
                    del bucket[t]
                if not bucket:
                    del self._data[vk]


class RedisVault:
    """Optional Redis-backed vault."""

    def __init__(
        self,
        redis_url: str,
        ttl_seconds: int,
        prefix: str = "shieldai:vault:",
        encryption_key: str | None = None,
    ) -> None:
        import redis.asyncio as redis

        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._ttl = ttl_seconds
        self._prefix = prefix
        self._cipher = build_cipher(encryption_key)

    @property
    def encryption_enabled(self) -> bool:
        return bool(getattr(self._cipher, "enabled", False))

    def _k(self, vault_key: str, token: str) -> str:
        return f"{self._prefix}{vault_key}:{token}"

    async def put(self, vault_key: str, token: str, original: str, entity_type: str) -> None:
        import json

        payload = json.dumps({"o": self._cipher.encrypt(original), "t": entity_type})
        await self._redis.set(self._k(vault_key, token), payload, ex=self._ttl)

    async def get(self, vault_key: str, token: str) -> str | None:
        import json

        raw = await self._redis.get(self._k(vault_key, token))
        if not raw:
            return None
        data = json.loads(raw)
        return self._cipher.decrypt(str(data.get("o")))

    async def clear_key(self, vault_key: str) -> None:
        pattern = f"{self._prefix}{vault_key}:*"
        async for key in self._redis.scan_iter(match=pattern):
            await self._redis.delete(key)

    async def mapping_count(self, vault_key: str) -> int:
        pattern = f"{self._prefix}{vault_key}:*"
        n = 0
        async for _ in self._redis.scan_iter(match=pattern):
            n += 1
        return n


def build_vault(settings) -> PiiVault:
    enc_key = getattr(settings, "vault_encryption_key", "") or None
    if settings.redis_url:
        return RedisVault(
            settings.redis_url,
            int(settings.vault_ttl_seconds),
            encryption_key=enc_key,
        )
    return DictVault(float(settings.vault_ttl_seconds), encryption_key=enc_key)
