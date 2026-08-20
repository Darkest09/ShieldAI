"""Reverse tokenization using the per-request vault."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.proxy.strategies import TOKEN_RE

if TYPE_CHECKING:
    from app.core.vault import PiiVault


async def deanonymize_text(text: str, *, vault: PiiVault, vault_key: str) -> str:
    out: list[str] = []
    pos = 0
    for m in TOKEN_RE.finditer(text):
        out.append(text[pos : m.start()])
        token = m.group(0)
        original = await vault.get(vault_key, token)
        out.append(original if original is not None else token)
        pos = m.end()
    out.append(text[pos:])
    return "".join(out)
