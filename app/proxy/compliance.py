"""Compliance enforcement module for the Privacy-Preserving AI Gateway.

Two responsibilities:

1. **Control mapping** — maps the gateway's capabilities to the regulatory
   regimes named in the proposal (NRB Cyber Resilience Guidelines, Nepal's
   Individual Privacy Act 2018, ISO/IEC 27001, NIST SP 800-207 Zero Trust) so a
   compliance coverage report can be produced on demand.

2. **Policy-rule engine** — evaluates each request against configurable,
   compliance-linked rules and decides an action (redact / warn / hold / block),
   returning a human-readable explanation and the regulatory basis.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Tier names <-> ordinal (mirrors app/core/models.SemanticRiskTier)
_TIER_ORD = {"low": 1, "medium": 2, "high": 3, "critical": 4}

# Action severity ordering (higher wins when multiple rules match).
_ACTION_SEVERITY = {"allow": 0, "redact": 1, "warn": 2, "hold": 3, "block": 4}


# --- Regulatory control catalogue -------------------------------------------

# control_id -> (regime, requirement, the gateway capability that satisfies it)
CONTROL_CATALOGUE: list[dict[str, str]] = [
    {
        "id": "NRB-CR-3.1",
        "regime": "NRB Cyber Resilience Guidelines",
        "requirement": "Confidentiality of customer data in transit to third parties",
        "capability": "PII detection + reversible tokenisation before upstream send",
        "status": "implemented",
    },
    {
        "id": "NRB-CR-4.2",
        "regime": "NRB Cyber Resilience Guidelines",
        "requirement": "Access management and least-privilege for sensitive systems",
        "capability": "Zero-Trust JWT auth + role-based access control",
        "status": "implemented",
    },
    {
        "id": "NRB-CR-5.4",
        "regime": "NRB Cyber Resilience Guidelines",
        "requirement": "Audit logging and incident investigation support",
        "capability": "Tamper-evident SHA-256 hash-chained audit trail",
        "status": "implemented",
    },
    {
        "id": "NRB-CR-6.1",
        "regime": "NRB Cyber Resilience Guidelines",
        "requirement": "Continuous risk monitoring and alerting",
        "capability": "Per-request context risk scoring + critical alert ring",
        "status": "implemented",
    },
    {
        "id": "IPA-2018-S3",
        "regime": "Individual Privacy Act 2018",
        "requirement": "Protection of personal data from unauthorised disclosure",
        "capability": "Anonymisation of PII (incl. citizenship, mobile) before AI processing",
        "status": "implemented",
    },
    {
        "id": "IPA-2018-S5",
        "regime": "Individual Privacy Act 2018",
        "requirement": "Data minimisation — collect/expose only what is necessary",
        "capability": "Tool payloads redacted; vault TTL; shadow-mode observability",
        "status": "implemented",
    },
    {
        "id": "IPA-2018-S12",
        "regime": "Individual Privacy Act 2018",
        "requirement": "Accountability and transparency of processing decisions",
        "capability": "Explainable policy decisions returned to the user",
        "status": "implemented",
    },
    {
        "id": "ISO-27001-A8.24",
        "regime": "ISO/IEC 27001",
        "requirement": "Use of cryptography to protect information at rest",
        "capability": "Optional AES-256-GCM encryption of vaulted PII",
        "status": "configurable",
    },
    {
        "id": "ISO-27001-A8.16",
        "regime": "ISO/IEC 27001",
        "requirement": "Monitoring activities for anomalous behaviour",
        "capability": "Injection heuristics + risk scoring + audit monitoring",
        "status": "implemented",
    },
    {
        "id": "NIST-800-207-T1",
        "regime": "NIST SP 800-207 Zero Trust",
        "requirement": "All data sources and computing services are resources to protect",
        "capability": "Every prompt treated as a potential exfiltration event",
        "status": "implemented",
    },
    {
        "id": "NIST-800-207-T4",
        "regime": "NIST SP 800-207 Zero Trust",
        "requirement": "Access determined by dynamic policy incl. behavioural attributes",
        "capability": "Context risk score + policy-rule engine per request",
        "status": "implemented",
    },
    {
        "id": "OWASP-LLM01",
        "regime": "OWASP Top 10 for LLM Applications",
        "requirement": "Prevent prompt injection from manipulating the model",
        "capability": "Heuristic prompt-injection scan (block/warn policy)",
        "status": "implemented",
    },
    {
        "id": "OWASP-LLM06",
        "regime": "OWASP Top 10 for LLM Applications",
        "requirement": "Prevent sensitive information disclosure to the model",
        "capability": "PII scrub + DLP policy rules before upstream send",
        "status": "implemented",
    },
]


# --- Policy rules ------------------------------------------------------------

DEFAULT_POLICIES: dict[str, Any] = {
    "rules": [
        {
            "id": "block-financial-secrets",
            "description": "Card numbers and live API secrets must never reach an AI provider.",
            "match": {"entities": ["CREDIT_CARD", "AWS_ACCESS_KEY_ID",
                                    "AWS_SECRET_ACCESS_KEY", "STRIPE_API_KEY"]},
            "action": "block",
            "basis": ["NRB-CR-3.1", "IPA-2018-S3", "OWASP-LLM06"],
        },
        {
            "id": "hold-sovereign-id",
            "description": "Citizenship numbers require human approval for lower-privilege roles.",
            "match": {"entities": ["NP_CITIZENSHIP_NUMBER"], "roles": ["teller", "officer"]},
            "action": "hold",
            "basis": ["IPA-2018-S3", "NRB-CR-4.2"],
        },
        {
            "id": "hold-critical-tier",
            "description": "Any critical-severity prompt is held for governance review.",
            "match": {"min_tier": "critical"},
            "action": "hold",
            "basis": ["NIST-800-207-T4", "NRB-CR-6.1"],
        },
        {
            "id": "default-redact",
            "description": "All other detected PII is anonymised (reversible tokens) before send.",
            "match": {"min_tier": "low"},
            "action": "redact",
            "basis": ["IPA-2018-S3", "OWASP-LLM06"],
        },
    ]
}


@dataclass
class PolicyDecision:
    action: str = "redact"
    matched_rules: list[str] = field(default_factory=list)
    basis: list[str] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "matched_rules": self.matched_rules,
            "regulatory_basis": self.basis,
            "explanation": self.explanation,
        }


def load_policies(path_str: str) -> dict[str, Any]:
    p = Path(path_str)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(DEFAULT_POLICIES, indent=2), encoding="utf-8")
        return json.loads(json.dumps(DEFAULT_POLICIES))
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — corrupt file shouldn't take the gateway down
        return json.loads(json.dumps(DEFAULT_POLICIES))


def _rule_matches(
    match: dict[str, Any],
    *,
    entities: set[str],
    tier_ord: int,
    role: str,
    injection: bool,
) -> bool:
    if "injection" in match and bool(match["injection"]) != injection:
        return False
    if "entities" in match:
        if not entities.intersection(set(match["entities"])):
            return False
    if "min_tier" in match:
        if tier_ord < _TIER_ORD.get(str(match["min_tier"]).lower(), 1):
            return False
    if "roles" in match:
        if role not in set(match["roles"]):
            return False
    return True


def evaluate_policies(
    policies: dict[str, Any],
    *,
    entities: set[str],
    semantic_tier: str,
    role: str,
    injection: bool,
) -> PolicyDecision:
    """Return the most-severe matching action plus its compliance basis."""
    # Nothing sensitive detected -> nothing to act on.
    if not entities and not injection:
        return PolicyDecision(
            action="allow", explanation="No PII or injection detected; passthrough."
        )

    tier_ord = _TIER_ORD.get(str(semantic_tier).lower(), 1)
    best = PolicyDecision(action="allow", explanation="No policy matched; passthrough.")
    best_sev = -1
    basis: list[str] = []
    matched: list[str] = []

    for rule in policies.get("rules", []):
        match = rule.get("match", {}) or {}
        if not _rule_matches(
            match, entities=entities, tier_ord=tier_ord, role=role, injection=injection
        ):
            continue
        matched.append(rule["id"])
        basis.extend(rule.get("basis", []))
        sev = _ACTION_SEVERITY.get(rule.get("action", "redact"), 1)
        if sev > best_sev:
            best_sev = sev
            best = PolicyDecision(
                action=rule.get("action", "redact"),
                explanation=rule.get("description", ""),
            )

    if best_sev < 0:
        # Nothing matched and no PII — allow.
        return best

    best.matched_rules = matched
    best.basis = sorted(set(basis))
    return best


def compliance_report(policies: dict[str, Any]) -> dict[str, Any]:
    """Coverage summary grouped by regulatory regime."""
    by_regime: dict[str, dict[str, Any]] = {}
    for ctrl in CONTROL_CATALOGUE:
        regime = ctrl["regime"]
        bucket = by_regime.setdefault(regime, {"controls": [], "implemented": 0, "total": 0})
        bucket["controls"].append(ctrl)
        bucket["total"] += 1
        if ctrl["status"] == "implemented":
            bucket["implemented"] += 1

    total = len(CONTROL_CATALOGUE)
    implemented = sum(1 for c in CONTROL_CATALOGUE if c["status"] == "implemented")
    return {
        "summary": {
            "controls_total": total,
            "controls_implemented": implemented,
            "coverage_pct": round(100 * implemented / total, 1) if total else 0.0,
            "active_policy_rules": len(policies.get("rules", [])),
        },
        "by_regime": by_regime,
    }
