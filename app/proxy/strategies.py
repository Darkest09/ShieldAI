"""Outward token forms for the three anonymization strategies.

All forms remain **reversible** via the per-request vault — the vault maps
``token -> original`` regardless of how the token looks. The strategy only
changes what the upstream model sees:

- ``placeholder`` → opaque sequential ``[SHIELD_p_00001]``
- ``mask``        → entity-typed ``[SHIELD_m_EMAIL_ADDRESS_00001]`` (model
  learns *what kind* of value was redacted, improving response quality)
- ``hash``        → deterministic salted digest ``[SHIELD_h_a1b2c3d4]`` so the
  same original yields the same token within a request (coreference-stable)
"""

from __future__ import annotations

import hashlib
import re

from app.core.settings import AnonymizationStrategy

_PREFIX: dict[AnonymizationStrategy, str] = {
    AnonymizationStrategy.placeholder: "p",
    AnonymizationStrategy.mask: "m",
    AnonymizationStrategy.hash: "h",
}

# Matches every outward form produced by ``make_token`` so postflight can reverse
# them: ``[SHIELD_<strategy-letter>_<alnum/underscore payload>]``.
TOKEN_RE = re.compile(r"\[SHIELD_[a-z]_[A-Za-z0-9_]+\]")


def make_token(
    strategy: AnonymizationStrategy,
    *,
    entity_type: str,
    original: str,
    counter: list[int],
    salt: str = "shieldai-v1",
) -> str:
    """Build the reversible token that replaces ``original`` upstream.

    ``counter`` is a single-element list used as a mutable sequential counter
    shared across one text body (ignored by the deterministic hash strategy).
    """
    prefix = _PREFIX.get(strategy, "p")

    if strategy == AnonymizationStrategy.hash:
        digest = hashlib.sha256(f"{salt}:{original}".encode("utf-8")).hexdigest()[:8]
        return f"[SHIELD_{prefix}_{digest}]"

    if strategy == AnonymizationStrategy.mask:
        et = re.sub(r"[^A-Z0-9]+", "_", entity_type.upper()).strip("_") or "PII"
        counter[0] += 1
        return f"[SHIELD_{prefix}_{et}_{counter[0]:05d}]"

    counter[0] += 1
    return f"[SHIELD_{prefix}_{counter[0]:05d}]"
