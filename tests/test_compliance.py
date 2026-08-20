from app.proxy.compliance import (
    DEFAULT_POLICIES,
    compliance_report,
    evaluate_policies,
)


def test_block_financial_secrets() -> None:
    d = evaluate_policies(
        DEFAULT_POLICIES, entities={"CREDIT_CARD"}, semantic_tier="high",
        role="officer", injection=False,
    )
    assert d.action == "block"
    assert "block-financial-secrets" in d.matched_rules
    assert d.basis  # regulatory basis is attached


def test_hold_citizenship_for_teller() -> None:
    d = evaluate_policies(
        DEFAULT_POLICIES, entities={"NP_CITIZENSHIP_NUMBER"}, semantic_tier="critical",
        role="teller", injection=False,
    )
    assert d.action == "hold"


def test_redact_low_tier_pii() -> None:
    d = evaluate_policies(
        DEFAULT_POLICIES, entities={"EMAIL_ADDRESS"}, semantic_tier="low",
        role="admin", injection=False,
    )
    assert d.action == "redact"


def test_allow_when_no_pii() -> None:
    d = evaluate_policies(
        DEFAULT_POLICIES, entities=set(), semantic_tier="low",
        role="admin", injection=False,
    )
    assert d.action == "allow"


def test_compliance_report_shape() -> None:
    rep = compliance_report(DEFAULT_POLICIES)
    assert rep["summary"]["controls_total"] > 0
    assert 0 <= rep["summary"]["coverage_pct"] <= 100
    assert "NRB Cyber Resilience Guidelines" in rep["by_regime"]
    assert "Individual Privacy Act 2018" in rep["by_regime"]
