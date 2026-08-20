"""Zero-Trust authentication endpoints — issue and introspect access tokens."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from app.proxy.identity import (
    TokenError,
    generate_totp_secret,
    issue_jwt,
    otpauth_uri,
    verify_jwt,
    verify_totp,
)

router = APIRouter(tags=["auth"])


def _require_bearer(request: Request, authorization: str | None) -> dict:
    settings = request.app.state.settings
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        return verify_jwt(token, secret=settings.jwt_secret, issuer=settings.jwt_issuer)
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc


class TokenRequest(BaseModel):
    username: str
    password: str
    totp_code: str | None = None


class MfaVerifyRequest(BaseModel):
    totp_code: str


async def _parse_credentials(request: Request) -> TokenRequest:
    """Accept either JSON or OAuth2 'password' grant (form-urlencoded)."""
    ctype = request.headers.get("content-type", "")
    if "application/json" in ctype:
        data = await request.json()
        return TokenRequest(**data)
    # OAuth2 password grant: grant_type=password&username=&password=&totp_code=
    from urllib.parse import parse_qs

    raw = (await request.body()).decode("utf-8", errors="replace")
    qs = {k: v[0] for k, v in parse_qs(raw).items()}
    return TokenRequest(
        username=qs.get("username", ""),
        password=qs.get("password", ""),
        totp_code=qs.get("totp_code") or qs.get("otp"),
    )


@router.post("/v1/auth/token")
async def issue_token(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    users = request.app.state.users
    body = await _parse_credentials(request)

    user = users.authenticate(body.username, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # MFA: required only if globally enabled AND the user enrolled a TOTP secret.
    if settings.mfa_enabled and user.totp_secret:
        if not body.totp_code or not verify_totp(body.totp_code, user.totp_secret):
            raise HTTPException(status_code=401, detail="Invalid or missing MFA code")

    token = issue_jwt(
        subject=user.username,
        role=user.role,
        secret=settings.jwt_secret,
        issuer=settings.jwt_issuer,
        ttl_seconds=settings.jwt_ttl_seconds,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "expires_in": settings.jwt_ttl_seconds,
    }


@router.get("/v1/auth/me")
async def whoami(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    claims = _require_bearer(request, authorization)
    return {"subject": claims["sub"], "role": claims["role"], "expires_at": claims["exp"]}


@router.post("/v1/auth/mfa/enroll")
async def mfa_enroll(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Begin TOTP enrollment: returns a secret + otpauth URI for a QR code.

    The secret is stored but only becomes enforced after /mfa/verify confirms a
    code, proving the authenticator app is synced.
    """
    claims = _require_bearer(request, authorization)
    settings = request.app.state.settings
    users = request.app.state.users
    secret = generate_totp_secret()
    if not users.set_totp_secret(claims["sub"], secret):
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "secret": secret,
        "otpauth_uri": otpauth_uri(secret, account=claims["sub"], issuer=settings.jwt_issuer),
        "next": "POST /v1/auth/mfa/verify with a current 6-digit code to confirm.",
    }


@router.post("/v1/auth/mfa/verify")
async def mfa_verify(
    request: Request,
    body: MfaVerifyRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Confirm TOTP enrollment by verifying a current code."""
    claims = _require_bearer(request, authorization)
    users = request.app.state.users
    user = users.get(claims["sub"])
    if user is None or not user.totp_secret:
        raise HTTPException(status_code=400, detail="No enrollment in progress; call /mfa/enroll")
    if not verify_totp(body.totp_code, user.totp_secret):
        raise HTTPException(status_code=401, detail="Code did not match")
    return {"mfa_enrolled": True, "subject": claims["sub"]}
