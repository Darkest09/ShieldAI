"""Security event correlation — turns individual request signals into incidents.

The audit log records single events; this engine looks across a sliding window
of recent requests to surface *patterns* a single event can't show: a subject
making repeated high-risk requests, bursts of prompt-injection attempts, or
rapid privilege-tier escalation. Feeds the proposal's "security event
correlation" and "suspicious behaviour detection" requirements.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Event:
    ts: float
    subject: str
    role: str
    risk_score: int
    injection: bool
    semantic_tier: str
    corr_id: str


@dataclass
class CorrelationEngine:
    window_seconds: float = 300.0
    max_events: int = 2000
    high_risk_threshold: int = 60
    burst_count: int = 3
    _events: deque[_Event] = field(default_factory=lambda: deque(maxlen=2000))

    def record(
        self,
        *,
        subject: str,
        role: str,
        risk_score: int,
        injection: bool,
        semantic_tier: str,
        corr_id: str,
    ) -> None:
        self._events.append(
            _Event(time.time(), subject, role, risk_score, injection, semantic_tier, corr_id)
        )

    def _recent(self) -> list[_Event]:
        cutoff = time.time() - self.window_seconds
        return [e for e in self._events if e.ts >= cutoff]

    def correlations(self) -> list[dict[str, Any]]:
        """Derive correlated incidents from the current window."""
        recent = self._recent()
        by_subject: dict[str, list[_Event]] = {}
        for e in recent:
            by_subject.setdefault(e.subject, []).append(e)

        incidents: list[dict[str, Any]] = []
        for subject, events in by_subject.items():
            high = [e for e in events if e.risk_score >= self.high_risk_threshold]
            injections = [e for e in events if e.injection]
            tiers = [e.semantic_tier for e in events]

            if len(high) >= self.burst_count:
                incidents.append({
                    "type": "repeated_high_risk",
                    "subject": subject,
                    "count": len(high),
                    "window_seconds": self.window_seconds,
                    "severity": "high",
                    "correlation_ids": [e.corr_id for e in high[-10:]],
                    "detail": f"{len(high)} high-risk requests from '{subject}' in window",
                })
            if len(injections) >= 2:
                incidents.append({
                    "type": "injection_burst",
                    "subject": subject,
                    "count": len(injections),
                    "severity": "critical",
                    "correlation_ids": [e.corr_id for e in injections[-10:]],
                    "detail": f"{len(injections)} prompt-injection attempts from '{subject}'",
                })
            if "critical" in tiers and {"low", "medium"} & set(tiers):
                incidents.append({
                    "type": "risk_escalation",
                    "subject": subject,
                    "severity": "medium",
                    "detail": f"'{subject}' escalated from low/medium to critical-tier prompts",
                })
        return incidents

    def summary(self) -> dict[str, Any]:
        recent = self._recent()
        return {
            "window_seconds": self.window_seconds,
            "events_in_window": len(recent),
            "subjects": len({e.subject for e in recent}),
            "incidents": self.correlations(),
        }
