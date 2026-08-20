"""Pre-flight PII detection and reversible tokenization."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from langchain_core.runnables import RunnableLambda

from app.core.models import ScrubStats
from app.core.settings import AnonymizationStrategy
from app.proxy.strategies import make_token

if TYPE_CHECKING:
    from presidio_analyzer import AnalyzerEngine

    from app.core.vault import PiiVault


PresidioAnalyzeFn = Callable[..., Awaitable[list[Any]]]


async def presidio_analyze_async(
    engine: "AnalyzerEngine", *, text: str, language: str = "en"
) -> list[Any]:
    """Runs `AnalyzerEngine.analyze` off the asyncio event loop."""
    return await asyncio.to_thread(engine.analyze, text=text, language=language)

_PLACEHOLDER_RE = RunnableLambda(
    lambda messages: "\n".join(
        f"{m.get('role','')}:{_flatten_content(m)}"
        for m in messages
        if m.get("role") != "tool"
    )
)


def _flatten_content(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                chunks.append(str(block.get("text", "")))
            elif isinstance(block, str):
                chunks.append(block)
        return "\n".join(chunks)
    if content is None:
        return ""
    return json.dumps(content, ensure_ascii=False)


def _pick_non_overlapping(results):
    ordered = sorted(results, key=lambda r: (-r.score, -(r.end - r.start)))
    picked = []
    for r in ordered:
        if any(
            r.start < e and r.end > s for s, e in ((p.start, p.end) for p in picked)
        ):
            continue
        picked.append(r)
    picked.sort(key=lambda r: r.start)
    return picked


async def scrub_text(
    *,
    text: str,
    engine: AnalyzerEngine,
    vault: PiiVault | None,
    vault_key: str,
    strategy: AnonymizationStrategy,
    shadow_mode: bool,
    analyze_fn: PresidioAnalyzeFn | None = None,
    salt: str = "shieldai-v1",
) -> tuple[str, ScrubStats]:
    runner = analyze_fn or presidio_analyze_async
    results = await runner(engine, text=text, language="en")
    picked = _pick_non_overlapping(results)
    by_type: dict[str, int] = {}
    for r in picked:
        et = str(r.entity_type)
        by_type[et] = by_type.get(et, 0) + 1
    stats = ScrubStats(entity_count=len(picked), by_type=by_type)
    stats.recompute_semantic_max_from_counts()

    if shadow_mode:
        return text, stats

    if vault is None:
        raise RuntimeError("vault required when shadow_mode is disabled")

    counter = [0]
    out = text
    for r in sorted(picked, key=lambda x: x.start, reverse=True):
        start, end = r.start, r.end
        original = out[start:end]
        entity = str(r.entity_type)
        token = make_token(
            strategy,
            entity_type=entity,
            original=original,
            counter=counter,
            salt=salt,
        )
        await vault.put(vault_key, token, original, entity)
        out = out[:start] + token + out[end:]
    return out, stats


async def scrub_request_messages(
    messages: list[dict],
    *,
    engine: AnalyzerEngine,
    vault: PiiVault | None,
    vault_key: str,
    strategy: AnonymizationStrategy,
    shadow_mode: bool,
    analyze_fn: PresidioAnalyzeFn | None = None,
    salt: str = "shieldai-v1",
) -> tuple[list[dict], ScrubStats]:
    _ = _PLACEHOLDER_RE.invoke(messages)
    new_messages: list[dict] = []
    aggregate = ScrubStats()
    for m in messages:
        role = m.get("role")
        if role == "tool":
            redacted = {
                "role": "tool",
                "content": "[SHIELD_TOOL_REDACTED]",
                "tool_call_id": m.get("tool_call_id"),
            }
            if "name" in m:
                redacted["name"] = m["name"]
            new_messages.append(redacted)
            continue

        content = m.get("content")
        if isinstance(content, str):
            scrubbed, st = await scrub_text(
                text=content,
                engine=engine,
                vault=vault,
                vault_key=vault_key,
                strategy=strategy,
                shadow_mode=shadow_mode,
                analyze_fn=analyze_fn,
                salt=salt,
            )
            aggregate.entity_count += st.entity_count
            for k, v in st.by_type.items():
                aggregate.by_type[k] = aggregate.by_type.get(k, 0) + v
            nm = dict(m)
            nm["content"] = scrubbed
            new_messages.append(nm)
        elif isinstance(content, list):
            new_parts: list[dict] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    scrubbed, st = await scrub_text(
                        text=str(block.get("text", "")),
                        engine=engine,
                        vault=vault,
                        vault_key=vault_key,
                        strategy=strategy,
                        shadow_mode=shadow_mode,
                        analyze_fn=analyze_fn,
                        salt=salt,
                    )
                    aggregate.entity_count += st.entity_count
                    for k, v in st.by_type.items():
                        aggregate.by_type[k] = aggregate.by_type.get(k, 0) + v
                    nb = dict(block)
                    nb["text"] = scrubbed
                    new_parts.append(nb)
                else:
                    new_parts.append(block)
            nm = dict(m)
            nm["content"] = new_parts
            new_messages.append(nm)
        else:
            nm = dict(m)
            if content is None:
                nm["content"] = ""
            elif isinstance(content, dict):
                nm["content"] = json.dumps(content)
            else:
                nm["content"] = json.dumps(content, default=str)
            new_messages.append(nm)
    aggregate.recompute_semantic_max_from_counts()
    return new_messages, aggregate
