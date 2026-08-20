"""Optional AES-256-GCM encryption for vaulted PII (ISO/IEC 27001 A.8.24).

The vault holds the token->original mappings needed to de-anonymise responses.
When a 32-byte key is configured AND the `cryptography` package is available,
originals are encrypted at rest in memory with AES-256-GCM. Otherwise the cipher
degrades to a transparent pass-through so local, zero-dependency runs still work
(the mapping is still TTL-bounded and never written to disk).
"""

from __future__ import annotations

import base64


class _NullCipher:
    """Transparent cipher used when encryption is not configured/available."""

    enabled = False

    def encrypt(self, plaintext: str) -> str:
        return plaintext

    def decrypt(self, token: str) -> str:
        return token


class _AesGcmCipher:
    enabled = True

    def __init__(self, key: bytes) -> None:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import os

        self._aesgcm = AESGCM(key)
        self._os = os

    def encrypt(self, plaintext: str) -> str:
        nonce = self._os.urandom(12)
        ct = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ct).decode("ascii")

    def decrypt(self, token: str) -> str:
        raw = base64.b64decode(token)
        nonce, ct = raw[:12], raw[12:]
        return self._aesgcm.decrypt(nonce, ct, None).decode("utf-8")


def build_cipher(key_b64: str | None):
    """Return an AES-256-GCM cipher if a valid 32-byte key + lib are present.

    Falls back to a null (pass-through) cipher otherwise, so the gateway never
    fails to start merely because encryption is unconfigured.
    """
    if not key_b64:
        return _NullCipher()
    try:
        key = base64.b64decode(key_b64)
        if len(key) != 32:
            return _NullCipher()
        return _AesGcmCipher(key)
    except Exception:  # noqa: BLE001 — missing lib or bad key -> safe fallback
        return _NullCipher()


def generate_key_b64() -> str:
    """Helper to mint a fresh base64 256-bit key for VAULT_ENCRYPTION_KEY."""
    import os

    return base64.b64encode(os.urandom(32)).decode("ascii")
