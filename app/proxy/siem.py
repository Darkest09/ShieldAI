"""SIEM integration — export audit events in CEF and optionally forward them.

Rather than run a full Elasticsearch/Kibana stack, the gateway emits its
tamper-evident audit trail in ArcSight **CEF** (Common Event Format), which
Splunk, QRadar, Elastic, and most SIEMs ingest natively, and can forward events
to a SIEM HTTP collector webhook.
"""

from __future__ import annotations

import json
from typing import Any

_CEF_HEADER = "CEF:0|ShieldAI|PPAG|0.1|{sig}|{name}|{sev}|"

# Map gateway risk level -> CEF severity (0-10).
_SEV = {"low": 2, "medium": 5, "high": 8, "critical": 10}


def _escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("=", "\\=")


def event_to_cef(ev: dict[str, Any]) -> str:
    risk = str(ev.get("risk_level", "low")).lower()
    sem = str(ev.get("semantic_risk", "low")).lower()
    sev = max(_SEV.get(risk, 2), _SEV.get(sem, 2))
    threats = ev.get("threats") or []
    sig = "injection" if threats else "pii_scrub"
    name = "Prompt injection blocked" if threats else "PII detected and scrubbed"
    pii_types = ",".join(sorted((ev.get("pii_types") or {}).keys())) or "none"
    ext = (
        f"rt={_escape(ev.get('time', ''))} "
        f"cs1Label=correlationId cs1={_escape(ev.get('correlation_id', ''))} "
        f"cs2Label=piiTypes cs2={_escape(pii_types)} "
        f"cs3Label=semanticRisk cs3={_escape(sem)} "
        f"cn1Label=scrubEntities cn1={int(ev.get('scrub_entities', 0))} "
        f"cs4Label=threats cs4={_escape(','.join(threats) or 'none')} "
        f"cs5Label=shadowMode cs5={_escape(str(ev.get('shadow_mode', False)))}"
    )
    return _CEF_HEADER.format(sig=sig, name=name, sev=sev) + ext


def events_to_cef(events: list[dict[str, Any]]) -> str:
    return "\n".join(event_to_cef(e) for e in events)


async def forward_to_siem(
    client, webhook_url: str, events: list[dict[str, Any]], *, fmt: str = "cef"
) -> dict[str, Any]:
    """POST events to a SIEM HTTP collector. Returns a small status dict."""
    if fmt == "cef":
        payload = events_to_cef(events)
        headers = {"Content-Type": "text/plain"}
        body = payload
    else:
        body = json.dumps({"events": events})
        headers = {"Content-Type": "application/json"}
    resp = await client.post(webhook_url, content=body, headers=headers, timeout=10.0)
    return {"forwarded": len(events), "status_code": resp.status_code}
