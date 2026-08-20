"""Zero-Trust identity & access layer for the Privacy-Preserving AI Gateway.

Implements, with the Python standard library only (no extra dependencies):

- HS256 JSON Web Tokens (issue + verify) for stateless access control.
- PBKDF2-HMAC-SHA256 password hashing for the local user store.
- RFC 6238 TOTP verification for optional multi-factor authentication.
- Role-based access control (RBAC) roles and a per-request context risk score.

"Never trust, always verify": every protected request re-verifies the token,
the role's permission, and the contextual risk of the prompt before it is
allowed to reach an AI provider.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --- Roles & permissions -----------------------------------------------------

# Role -> the maximum semantic risk tier that role is allowed to send upstream.
# (tiers: low=1, medium=2, high=3, critical=4 — see app/core/models.py)
ROLE_MAX_TIER: dict[str, int] = {
    "admin": 4,      # security admin — may override, sees everything
    "analyst": 3,    # SOC analyst — high allowed, critical held for approval
    "officer": 2,    # banking officer — medium and below
    "teller": 1,     # front-desk — low only; everything else blocked/held
}

VALID_ROLES = frozenset(ROLE_MAX_TIER)


# --- Base64url helpers -------------------------------------------------------

def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


# --- JWT (HS256) -------------------------------------------------------------

def issue_jwt(
    *,
    subject: str,
    role: str,
    secret: str,
    issuer: str,
    ttl_seconds: int,
    extra: dict[str, Any] | None = None,
) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iss": issuer,
        "iat": now,
        "exp": now + int(ttl_seconds),
    }
    if extra:
        payload.update(extra)
    segments = [
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode()),
        _b64url_encode(json.dumps(payload, separators=(",", ":")).encode()),
    ]
    signing_input = ".".join(segments).encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    segments.append(_b64url_encode(sig))
    return ".".join(segments)


class TokenError(Exception):
    """Raised when a JWT is malformed, mis-signed, or expired."""


def verify_jwt(token: str, *, secret: str, issuer: str) -> dict[str, Any]:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError as exc:
        raise TokenError("Malformed token") from exc

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64url_decode(sig_b64)):
        raise TokenError("Bad signature")

    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception as exc:  # noqa: BLE001
        raise TokenError("Bad payload") from exc

    if payload.get("iss") != issuer:
        raise TokenError("Wrong issuer")
    if int(payload.get("exp", 0)) < int(time.time()):
        raise TokenError("Token expired")
    if payload.get("role") not in VALID_ROLES:
        raise TokenError("Unknown role")
    return payload


# --- Password hashing (PBKDF2) ----------------------------------------------

def hash_password(password: str, *, iterations: int = 200_000) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64url_encode(salt)}${_b64url_encode(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), _b64url_decode(salt_b64), int(iters)
        )
        return hmac.compare_digest(dk, _b64url_decode(hash_b64))
    except Exception:  # noqa: BLE001
        return False


# --- TOTP (RFC 6238) ---------------------------------------------------------

def totp_now(secret_b32: str, *, step: int = 30, digits: int = 6, at: int | None = None) -> str:
    key = base64.b32decode(secret_b32.upper() + "=" * (-len(secret_b32) % 8))
    counter = int((at if at is not None else time.time()) // step)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % (10**digits)
    return str(code).zfill(digits)


def generate_totp_secret(length: int = 20) -> str:
    """Mint a fresh base32 TOTP secret for enrollment (no padding)."""
    return base64.b32encode(os.urandom(length)).decode("ascii").rstrip("=")


def otpauth_uri(secret_b32: str, *, account: str, issuer: str) -> str:
    """otpauth:// provisioning URI an authenticator app turns into a QR code."""
    from urllib.parse import quote

    label = quote(f"{issuer}:{account}")
    return (
        f"otpauth://totp/{label}?secret={secret_b32}"
        f"&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"
    )


def verify_totp(code: str, secret_b32: str, *, window: int = 1) -> bool:
    if not code or not code.isdigit():
        return False
    now = int(time.time())
    for drift in range(-window, window + 1):
        if hmac.compare_digest(code, totp_now(secret_b32, at=now + drift * 30)):
            return True
    return False


# --- User store --------------------------------------------------------------

@dataclass
class User:
    username: str
    role: str
    password_hash: str
    totp_secret: str | None = None  # base32; None == MFA not enrolled
    disabled: bool = False


class UserStore:
    """JSON-backed user directory. Seeds default banking-role users on first run."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._seed_defaults()

    def _seed_defaults(self) -> None:
        # Demo identities spanning the RBAC roles. Passwords are placeholders;
        # rotate via the store before any real deployment.
        defaults = {
            "admin":   {"role": "admin",   "password": "admin123"},
            "analyst": {"role": "analyst", "password": "analyst123"},
            "officer": {"role": "officer", "password": "officer123"},
            "teller":  {"role": "teller",  "password": "teller123"},
        }
        data = {
            u: {"role": v["role"], "password_hash": hash_password(v["password"]), "totp_secret": None}
            for u, v in defaults.items()
        }
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load(self) -> dict[str, dict[str, Any]]:
        return json.loads(self._path.read_text(encoding="utf-8"))

    def get(self, username: str) -> User | None:
        row = self._load().get(username)
        if not row:
            return None
        return User(
            username=username,
            role=row["role"],
            password_hash=row["password_hash"],
            totp_secret=row.get("totp_secret"),
            disabled=bool(row.get("disabled", False)),
        )

    def authenticate(self, username: str, password: str) -> User | None:
        user = self.get(username)
        if user and not user.disabled and verify_password(password, user.password_hash):
            return user
        return None

    def _mutate(self, username: str, **fields) -> bool:
        data = self._load()
        if username not in data:
            return False
        data[username].update(fields)
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return True

    def set_totp_secret(self, username: str, secret: str) -> bool:
        """Store a (not-yet-confirmed) TOTP secret during enrollment."""
        return self._mutate(username, totp_secret=secret)

    def set_password(self, username: str, password: str) -> bool:
        return self._mutate(username, password_hash=hash_password(password))

    def create_user(self, username: str, password: str, role: str) -> bool:
        if role not in VALID_ROLES:
            raise ValueError(f"Unknown role: {role}")
        data = self._load()
        if username in data:
            return False
        data[username] = {
            "role": role,
            "password_hash": hash_password(password),
            "totp_secret": None,
            "disabled": False,
        }
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return True

    def list_users(self) -> list[dict[str, Any]]:
        return [
            {
                "username": username,
                "role": row["role"],
                "disabled": bool(row.get("disabled", False)),
                "mfa_enrolled": bool(row.get("totp_secret")),
            }
            for username, row in sorted(self._load().items())
        ]

    def update_user(
        self,
        username: str,
        *,
        role: str | None = None,
        disabled: bool | None = None,
        password: str | None = None,
        reset_mfa: bool = False,
    ) -> bool:
        fields: dict[str, Any] = {}
        if role is not None:
            if role not in VALID_ROLES:
                raise ValueError(f"Unknown role: {role}")
            fields["role"] = role
        if disabled is not None:
            fields["disabled"] = disabled
        if password:
            fields["password_hash"] = hash_password(password)
        if reset_mfa:
            fields["totp_secret"] = None
        return self._mutate(username, **fields)


# --- Context-aware risk scoring ---------------------------------------------

@dataclass
class AccessContext:
    """The verified principal + computed risk for one request."""

    subject: str = "anonymous"
    role: str = "teller"
    authenticated: bool = False
    risk_score: int = 0           # 0-100
    risk_reasons: list[str] = field(default_factory=list)


def score_request_risk(
    *,
    role: str,
    semantic_tier: int,
    injection_hits: int,
    entity_count: int,
) -> tuple[int, list[str]]:
    """Continuous, context-aware risk score (0-100) — a Zero-Trust signal.

    Combines the worst PII severity, injection heuristics, PII volume, and the
    privilege of the role making the request. Higher = more dangerous.
    """
    score = 0
    reasons: list[str] = []

    tier_weight = {1: 5, 2: 20, 3: 45, 4: 70}.get(semantic_tier, 0)
    if tier_weight:
        score += tier_weight
        reasons.append(f"pii_tier={semantic_tier}")

    if injection_hits:
        score += min(40, 20 * injection_hits)
        reasons.append(f"injection_hits={injection_hits}")

    if entity_count >= 5:
        score += 15
        reasons.append("bulk_pii")
    elif entity_count > 0:
        score += 5

    # Lower-privilege roles handling sensitive data is riskier.
    allowed = ROLE_MAX_TIER.get(role, 1)
    if semantic_tier > allowed:
        score += 15
        reasons.append(f"role_over_privilege:{role}<tier{semantic_tier}")

    return min(100, score), reasons
