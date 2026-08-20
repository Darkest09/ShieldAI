"""Explainability & governance layer for the Privacy-Preserving AI Gateway.

Provides the human-in-the-loop approval workflow for high-risk prompts and the
structured, user-facing explanations the proposal requires ("transparent policy
explanations", "human approval workflows for high-risk prompts"). The gateway
explicitly rejects fully autonomous governance — an admin retains authority over
held requests.
"""

from __future__ import annotations

import itertools
import json
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ApprovalTicket:
    id: str
    correlation_id: str
    subject: str
    role: str
    reason: str
    risk_score: int
    matched_rules: list[str] = field(default_factory=list)
    basis: list[str] = field(default_factory=list)
    status: str = "pending"  # pending | approved | denied
    created_at: float = field(default_factory=time.time)
    decided_by: str | None = None
    decided_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "correlation_id": self.correlation_id,
            "subject": self.subject,
            "role": self.role,
            "reason": self.reason,
            "risk_score": self.risk_score,
            "matched_rules": self.matched_rules,
            "regulatory_basis": self.basis,
            "status": self.status,
            "created_at": self.created_at,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at,
        }


class ApprovalQueue:
    """In-memory, bounded queue of high-risk prompts awaiting human approval."""

    def __init__(
        self, max_entries: int = 512, ttl_seconds: float = 3600.0, store_path: str | None = None
    ) -> None:
        self._items: OrderedDict[str, ApprovalTicket] = OrderedDict()
        self._counter = itertools.count(1)
        self._max = max_entries
        self._ttl = ttl_seconds
        self._store = Path(store_path) if store_path else None
        self._load()

    def _load(self) -> None:
        if not self._store or not self._store.exists():
            return
        try:
            data = json.loads(self._store.read_text(encoding="utf-8"))
            maxn = 0
            for row in data:
                row = dict(row)
                row["basis"] = row.pop("regulatory_basis", [])  # to_dict() renames this
                t = ApprovalTicket(**row)
                self._items[t.id] = t
                try:
                    maxn = max(maxn, int(t.id.split("_")[-1]))
                except ValueError:
                    pass
            self._counter = itertools.count(maxn + 1)
        except Exception:  # noqa: BLE001
            pass

    def _save(self) -> None:
        if not self._store:
            return
        try:
            self._store.parent.mkdir(parents=True, exist_ok=True)
            self._store.write_text(
                json.dumps([t.to_dict() for t in self._items.values()], indent=2),
                encoding="utf-8",
            )
        except Exception:  # noqa: BLE001
            pass

    def _prune(self) -> None:
        now = time.time()
        for tid, t in list(self._items.items()):
            if now - t.created_at > self._ttl:
                del self._items[tid]
        while len(self._items) > self._max:
            self._items.popitem(last=False)

    def create(
        self,
        *,
        correlation_id: str,
        subject: str,
        role: str,
        reason: str,
        risk_score: int,
        matched_rules: list[str],
        basis: list[str],
    ) -> ApprovalTicket:
        self._prune()
        tid = f"appr_{next(self._counter):06d}"
        ticket = ApprovalTicket(
            id=tid,
            correlation_id=correlation_id,
            subject=subject,
            role=role,
            reason=reason,
            risk_score=risk_score,
            matched_rules=matched_rules,
            basis=basis,
        )
        self._items[tid] = ticket
        self._save()
        return ticket

    def get(self, ticket_id: str) -> ApprovalTicket | None:
        return self._items.get(ticket_id)

    def decide(self, ticket_id: str, *, approver: str, approve: bool) -> ApprovalTicket | None:
        ticket = self._items.get(ticket_id)
        if ticket is None:
            return None
        ticket.status = "approved" if approve else "denied"
        ticket.decided_by = approver
        ticket.decided_at = time.time()
        self._save()
        return ticket

    def pending(self) -> list[dict[str, Any]]:
        self._prune()
        return [t.to_dict() for t in self._items.values() if t.status == "pending"]

    def all(self, limit: int = 200) -> list[dict[str, Any]]:
        self._prune()
        items = list(self._items.values())[-limit:]
        return [t.to_dict() for t in reversed(items)]

    def is_approved(self, ticket_id: str, *, correlation_id: str | None = None) -> bool:
        ticket = self._items.get(ticket_id)
        if ticket is None or ticket.status != "approved":
            return False
        if correlation_id is not None and ticket.correlation_id != correlation_id:
            return False
        return True


def build_user_explanation(
    *,
    action: str,
    pii_types: dict[str, int],
    matched_rules: list[str],
    basis: list[str],
    risk_score: int,
) -> dict[str, Any]:
    """Transparent, user-facing explanation of what the gateway did and why."""
    kinds = ", ".join(sorted(pii_types)) or "none"
    verb = {
        "block": "blocked",
        "hold": "held for approval",
        "warn": "flagged",
        "redact": "anonymised before sending",
        "allow": "passed through",
    }.get(action, action)
    return {
        "action": action,
        "summary": f"Your prompt was {verb}.",
        "detected_pii": pii_types,
        "detected_pii_summary": kinds,
        "policy_rules": matched_rules,
        "regulatory_basis": basis,
        "risk_score": risk_score,
        "human_oversight": action == "hold",
    }
