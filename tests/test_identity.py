import time

import pytest

from app.proxy.identity import (
    TokenError,
    hash_password,
    issue_jwt,
    score_request_risk,
    totp_now,
    verify_jwt,
    verify_password,
    verify_totp,
)


def test_jwt_roundtrip_and_claims() -> None:
    tok = issue_jwt(subject="analyst1", role="analyst", secret="s", issuer="ppag", ttl_seconds=60)
    claims = verify_jwt(tok, secret="s", issuer="ppag")
    assert claims["sub"] == "analyst1"
    assert claims["role"] == "analyst"


def test_jwt_rejects_bad_signature() -> None:
    tok = issue_jwt(subject="x", role="admin", secret="right", issuer="ppag", ttl_seconds=60)
    with pytest.raises(TokenError):
        verify_jwt(tok, secret="wrong", issuer="ppag")


def test_jwt_rejects_expired() -> None:
    tok = issue_jwt(subject="x", role="admin", secret="s", issuer="ppag", ttl_seconds=-1)
    with pytest.raises(TokenError):
        verify_jwt(tok, secret="s", issuer="ppag")


def test_jwt_rejects_wrong_issuer() -> None:
    tok = issue_jwt(subject="x", role="admin", secret="s", issuer="ppag", ttl_seconds=60)
    with pytest.raises(TokenError):
        verify_jwt(tok, secret="s", issuer="other")


def test_password_hash_verify() -> None:
    h = hash_password("hunter2")
    assert verify_password("hunter2", h)
    assert not verify_password("nope", h)


def test_totp_verifies_current_window() -> None:
    secret = "JBSWY3DPEHPK3PXP"
    code = totp_now(secret)
    assert verify_totp(code, secret)
    assert not verify_totp("000000", secret)


def test_risk_score_monotonic() -> None:
    low, _ = score_request_risk(role="officer", semantic_tier=1, injection_hits=0, entity_count=1)
    high, reasons = score_request_risk(role="teller", semantic_tier=4, injection_hits=2, entity_count=6)
    assert high > low
    assert high >= 70
    assert any("pii_tier" in r for r in reasons)
