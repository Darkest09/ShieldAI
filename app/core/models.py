"""Domain models plus semantic PI severity labels (maps to Low / Medium / High / Critical)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any, Iterable


class SemanticRiskTier(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


_SEMANTIC_OVERRIDES: dict[str, SemanticRiskTier] = {
    # Low
    "EMAIL_ADDRESS": SemanticRiskTier.LOW,
    "URL": SemanticRiskTier.LOW,
    "DATE_TIME": SemanticRiskTier.LOW,
    # Medium — indirect identifiers / context
    "PHONE_NUMBER": SemanticRiskTier.MEDIUM,
    "NP_MOBILE_NUMBER": SemanticRiskTier.MEDIUM,
    "IP_ADDRESS": SemanticRiskTier.MEDIUM,
    "LOCATION": SemanticRiskTier.MEDIUM,
    "NRP": SemanticRiskTier.MEDIUM,
    "PERSON": SemanticRiskTier.MEDIUM,
    # High — financial
    "CREDIT_CARD": SemanticRiskTier.HIGH,
    "BANK_ACCOUNT_NUMBER": SemanticRiskTier.HIGH,
    "SWIFT_BIC_CODE": SemanticRiskTier.MEDIUM,
    # Critical — long-lived secrets & sovereign identifiers
    "AWS_ACCESS_KEY_ID": SemanticRiskTier.CRITICAL,
    "AWS_SECRET_ACCESS_KEY": SemanticRiskTier.CRITICAL,
    "STRIPE_API_KEY": SemanticRiskTier.CRITICAL,
    "NP_CITIZENSHIP_NUMBER": SemanticRiskTier.CRITICAL,
}


def semantic_risk_from_entity(entity_type: str) -> SemanticRiskTier:
    key = str(entity_type).strip().upper()
    return _SEMANTIC_OVERRIDES.get(key, SemanticRiskTier.MEDIUM)


def worst_semantic_tier(types_present: Iterable[str]) -> SemanticRiskTier:
    best = SemanticRiskTier.LOW
    seen = False
    for et in types_present:
        seen = True
        cand = semantic_risk_from_entity(et)
        if cand > best:
            best = cand
    return best if seen else SemanticRiskTier.LOW


def semantic_tier_to_label(tier: SemanticRiskTier) -> str:
    return tier.name.lower()


@dataclass
class ScrubStats:
    entity_count: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    semantic_max_risk: str = "low"

    def recompute_semantic_max_from_counts(self) -> None:
        w = worst_semantic_tier(self.by_type.keys())
        self.semantic_max_risk = semantic_tier_to_label(w)


@dataclass
class InjectionFinding:
    matched_rules: list[str] = field(default_factory=list)

    def should_block(self, policy) -> bool:
        if not self.matched_rules:
            return False
        pv = getattr(policy, "value", policy)
        return pv == "block"


@dataclass
class AuditEventPayload:
    correlation_id: str
    ts: datetime
    risk_level: str
    semantic_risk: str
    pii_kinds: dict[str, int]
    threats: list[str]
    scrub_stats: ScrubStats
    extra: dict[str, Any] = field(default_factory=dict)
