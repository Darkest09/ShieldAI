from app.core.encryption import build_cipher, generate_key_b64
from app.proxy.governance import ApprovalQueue, build_user_explanation


def test_approval_queue_lifecycle() -> None:
    q = ApprovalQueue()
    t = q.create(
        correlation_id="c1", subject="teller", role="teller", reason="critical pii",
        risk_score=80, matched_rules=["hold-critical-tier"], basis=["NIST-800-207-T4"],
    )
    assert not q.is_approved(t.id)
    assert t.to_dict() in q.pending()

    q.decide(t.id, approver="admin", approve=True)
    assert q.is_approved(t.id)
    assert q.is_approved(t.id, correlation_id="c1")
    assert not q.is_approved(t.id, correlation_id="other")
    # No longer pending once decided.
    assert all(p["id"] != t.id for p in q.pending())


def test_approval_denied_is_not_approved() -> None:
    q = ApprovalQueue()
    t = q.create(correlation_id="c", subject="x", role="officer", reason="r",
                 risk_score=50, matched_rules=[], basis=[])
    q.decide(t.id, approver="admin", approve=False)
    assert not q.is_approved(t.id)


def test_user_explanation_contents() -> None:
    exp = build_user_explanation(
        action="hold", pii_types={"NP_CITIZENSHIP_NUMBER": 1},
        matched_rules=["hold-sovereign-id"], basis=["IPA-2018-S3"], risk_score=72,
    )
    assert exp["action"] == "hold"
    assert exp["human_oversight"] is True
    assert "NP_CITIZENSHIP_NUMBER" in exp["detected_pii"]


def test_null_cipher_roundtrip_without_key() -> None:
    c = build_cipher(None)
    assert c.enabled is False
    assert c.decrypt(c.encrypt("secret")) == "secret"


def test_aes_cipher_roundtrip_if_available() -> None:
    c = build_cipher(generate_key_b64())
    # cryptography may or may not be installed; both paths must round-trip.
    assert c.decrypt(c.encrypt("nepali-secret")) == "nepali-secret"
