from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.models import InjectionFinding, ScrubStats, semantic_risk_from_entity
from app.core.settings import InjectionPolicy
from app.proxy.compliance import evaluate_policies
from app.proxy.governance import build_user_explanation
from app.proxy.identity import (
    AccessContext,
    TokenError,
    score_request_risk,
    verify_jwt,
)
from app.proxy.injection import scan_prompt_messages
from app.proxy.metrics import incr
from app.proxy.openai_schema import ChatCompletionRequest
from app.proxy.postflight import deanonymize_text
from app.proxy.preflight import presidio_analyze_async, scrub_request_messages
from app.proxy.rate_limit import RateLimitChecker
from app.proxy.upstream_client import chat_completions_endpoint, post_chat_completion

router = APIRouter()

CORR_HEADER = "X-ShieldAI-Correlation-ID"
RISK_HEADER = "X-ShieldAI-Risk-Score"


def _authenticate_shield_key(shield_key: str | None, settings) -> None:
    """Enforce the client Shield-key allowlist when one is configured.

    When ``SHIELD_API_KEYS`` is empty the proxy stays open (anonymous) so the
    demo chat and local grading keep working; set it to lock the gateway down.
    """
    allowed = settings.allowed_shield_keys()
    if not allowed:
        return
    if not shield_key or shield_key not in allowed:
        raise HTTPException(status_code=401, detail="Invalid or missing X-ShieldAI-Key")


def _resolve_principal(
    *, settings, shield_key: str | None, authorization: str | None
) -> AccessContext:
    """Zero-Trust verification of the caller ('never trust, always verify').

    - Always enforces the Shield-key allowlist when configured.
    - When ZERO_TRUST_ENABLED, additionally requires a valid Bearer JWT and
      derives the RBAC role from it. Otherwise falls back to an anonymous
      'officer' principal so the open demo keeps working.
    """
    _authenticate_shield_key(shield_key, settings)

    if not settings.zero_trust_enabled:
        return AccessContext(subject="anonymous", role="officer", authenticated=False)

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401, detail="Zero-Trust: missing Bearer access token"
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = verify_jwt(
            token, secret=settings.jwt_secret, issuer=settings.jwt_issuer
        )
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=f"Zero-Trust: {exc}") from exc
    return AccessContext(
        subject=str(claims["sub"]), role=str(claims["role"]), authenticated=True
    )


def _messages_as_dicts(body: ChatCompletionRequest) -> list[dict[str, Any]]:
    return [m.model_dump(mode="python", exclude_none=True) for m in body.messages]


def _serialize_for_budget(body: ChatCompletionRequest) -> str:
    return json.dumps(
        [m.model_dump(mode="json", exclude_none=True) for m in body.messages],
        ensure_ascii=False,
    )


def _prompt_snapshot(messages: list[dict[str, Any]]) -> str:
    return json.dumps(messages, ensure_ascii=False, indent=2)


def _effective_shadow(request: Request) -> bool:
    cfg = getattr(request.app.state, "config", {}) or {}
    settings = request.app.state.settings
    return bool(cfg.get("shadow_mode", settings.shadow_mode))


def _emit_critical_alerts(
    request: Request,
    *,
    corr_id: str,
    stats: ScrubStats,
    finding: InjectionFinding,
) -> None:
    ring = request.app.state.alert_ring
    if stats.semantic_max_risk.lower() == "critical":
        kinds = sorted(stats.by_type.keys())
        ring.push_critical(
            headline="Critical semantic PII detected",
            detail=f"Worst-tier entities in this request: {', '.join(kinds) or 'n/a'}",
            correlation_id=corr_id,
            source="presidio.semantic_risk",
        )
    if finding.matched_rules:
        ring.push_critical(
            headline="Prompt injection heuristic matched",
            detail=", ".join(finding.matched_rules),
            correlation_id=corr_id,
            source="injection.heuristic",
        )


async def _log_audit(
    request: Request,
    *,
    corr_id: str,
    finding: InjectionFinding,
    stats: ScrubStats,
    scrubbed: bool = True,
    shadow_mode_used: bool = False,
) -> None:
    risk = "low"
    if finding.matched_rules:
        policy = request.app.state.settings.injection_policy
        if policy == InjectionPolicy.warn:
            risk = "medium"
        elif policy == InjectionPolicy.block:
            risk = "high"

    semantic = stats.semantic_max_risk if scrubbed else "low"

    audit = request.app.state.audit
    kinds = stats.by_type if scrubbed else {}
    count = stats.entity_count if scrubbed else 0
    st = ScrubStats(entity_count=count, by_type=dict(kinds))
    st.semantic_max_risk = semantic if scrubbed else "low"

    audit.append_event(
        corr_id=corr_id,
        ts_iso=datetime.now(timezone.utc).isoformat(),
        risk_level=risk,
        semantic_risk=st.semantic_max_risk,
        shadow_mode_applied=shadow_mode_used,
        kinds_counts=dict(st.by_type),
        threats=list(finding.matched_rules),
        stats=st,
    )


async def _deanonymize_response(
    data: dict[str, Any], *, vault, vault_key: str
) -> str:
    """Reverse tokens across every choice's message content and tool-call args.

    Mutates ``data`` in place and returns the concatenated restored text (for
    response-token accounting).
    """
    restored_parts: list[str] = []
    for choice in data.get("choices") or []:
        msg = choice.get("message")
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if isinstance(content, str) and content:
            msg["content"] = await deanonymize_text(
                content, vault=vault, vault_key=vault_key
            )
            restored_parts.append(msg["content"])
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") if isinstance(tc, dict) else None
            if isinstance(fn, dict) and isinstance(fn.get("arguments"), str):
                fn["arguments"] = await deanonymize_text(
                    fn["arguments"], vault=vault, vault_key=vault_key
                )
                restored_parts.append(fn["arguments"])
    return "".join(restored_parts)


async def _sse_chunks(
    *,
    model: str,
    corr_id: str,
    deanonymized: str,
) -> AsyncIterator[bytes]:
    created = int(datetime.now(timezone.utc).timestamp())
    blobs = [
        {
            "id": corr_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": ""},
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": corr_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": deanonymized},
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": corr_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        },
    ]
    for c in blobs:
        yield f"data: {json.dumps(c, ensure_ascii=False)}\n\n".encode("utf-8")
    yield b"data: [DONE]\n\n"


@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    body: ChatCompletionRequest,
    x_shieldai_key: str | None = Header(default=None, alias="X-ShieldAI-Key"),
    authorization: str | None = Header(default=None),
    x_shieldai_approval: str | None = Header(default=None, alias="X-ShieldAI-Approval"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    x_device_trusted: str | None = Header(default=None, alias="X-Device-Trusted"),
):
    settings = request.app.state.settings
    principal = _resolve_principal(
        settings=settings, shield_key=x_shieldai_key, authorization=authorization
    )
    device_trusted = str(x_device_trusted).lower() in ("1", "true", "yes")
    corr_id = str(uuid.uuid4())
    vault_key = corr_id

    msgs = _messages_as_dicts(body)
    serialized = _serialize_for_budget(body)
    await RateLimitChecker.assert_within_budget(x_shieldai_key, serialized, settings)

    finding = scan_prompt_messages(msgs)
    shadow = _effective_shadow(request)

    if finding.should_block(settings.injection_policy):
        incr("threats_blocked")
        _emit_critical_alerts(
            request,
            corr_id=corr_id,
            stats=ScrubStats(),
            finding=finding,
        )
        await _log_audit(
            request,
            corr_id=corr_id,
            finding=finding,
            stats=ScrubStats(),
            scrubbed=False,
            shadow_mode_used=False,
        )
        raise HTTPException(status_code=422, detail="Prompt policy violation")

    engine = request.app.state.analyzer
    vault = request.app.state.vault

    # Presidio: bound here so chat traffic always uses asyncio.to_thread (non-blocking scrub).
    scrubbed_msgs, stats = await scrub_request_messages(
        msgs,
        engine=engine,
        vault=vault if not shadow else None,
        vault_key=vault_key,
        strategy=settings.anon_strategy,
        shadow_mode=shadow,
        analyze_fn=presidio_analyze_async,
        salt=settings.hash_salt,
    )

    if settings.prompt_debug_enabled:
        request.app.state.prompt_debug.put(
            corr_id,
            _prompt_snapshot(msgs),
            _prompt_snapshot(scrubbed_msgs),
        )

    incr("pii_intercepted", stats.entity_count)
    await _log_audit(
        request,
        corr_id=corr_id,
        finding=finding,
        stats=stats,
        scrubbed=True,
        shadow_mode_used=shadow,
    )

    _emit_critical_alerts(request, corr_id=corr_id, stats=stats, finding=finding)

    # --- Zero-Trust context risk + compliance policy decision ----------------
    tier_ord = max(
        (semantic_risk_from_entity(e).value for e in stats.by_type), default=1
    )
    risk_score, risk_reasons = score_request_risk(
        role=principal.role,
        semantic_tier=tier_ord,
        injection_hits=len(finding.matched_rules),
        entity_count=stats.entity_count,
    )
    # Device posture (Zero-Trust): an untrusted device handling sensitive data
    # raises the risk and can be required to be trusted for high tiers.
    if not device_trusted and tier_ord >= 2:
        risk_score = min(100, risk_score + 10)
        risk_reasons.append(f"untrusted_device:{x_device_id or 'unknown'}")
    principal.risk_score = risk_score
    principal.risk_reasons = risk_reasons

    # Record for cross-request security correlation.
    if hasattr(request.app.state, "correlator"):
        request.app.state.correlator.record(
            subject=principal.subject,
            role=principal.role,
            risk_score=risk_score,
            injection=bool(finding.matched_rules),
            semantic_tier=stats.semantic_max_risk,
            corr_id=corr_id,
        )

    policies = getattr(request.app.state, "policies", {"rules": []})
    decision = evaluate_policies(
        policies,
        entities=set(stats.by_type.keys()),
        semantic_tier=stats.semantic_max_risk,
        role=principal.role,
        injection=bool(finding.matched_rules),
    )
    # Trusted-device requirement upgrades a redact to a hold for high tiers.
    if (
        settings.zero_trust_enabled
        and settings.require_trusted_device
        and not device_trusted
        and tier_ord >= 3
        and decision.action in ("redact", "warn")
    ):
        decision.action = "hold"
        decision.matched_rules = [*decision.matched_rules, "require-trusted-device"]
        decision.explanation = "High-risk PII from an untrusted device requires approval."
    explanation = build_user_explanation(
        action=decision.action,
        pii_types=dict(stats.by_type),
        matched_rules=decision.matched_rules,
        basis=decision.basis,
        risk_score=risk_score,
    )

    # Enforcement is active only under Zero-Trust mode, so the open demo and the
    # existing test suite keep their scrub-and-send behaviour by default.
    if settings.zero_trust_enabled and decision.action in ("block", "hold"):
        approved = False
        if decision.action == "hold" and x_shieldai_approval:
            approved = request.app.state.approvals.is_approved(
                x_shieldai_approval, correlation_id=None
            )
        if not approved:
            await vault.clear_key(vault_key)
            if decision.action == "block":
                incr("threats_blocked")
                raise HTTPException(
                    status_code=422,
                    detail={"error": "Blocked by compliance policy", **explanation},
                )
            # hold -> create an approval ticket and return 423 Locked
            ticket = request.app.state.approvals.create(
                correlation_id=corr_id,
                subject=principal.subject,
                role=principal.role,
                reason=decision.explanation,
                risk_score=risk_score,
                matched_rules=decision.matched_rules,
                basis=decision.basis,
            )
            request.app.state.alert_ring.push_critical(
                headline="Prompt held for human approval",
                detail=f"{decision.explanation} (risk {risk_score})",
                correlation_id=corr_id,
                source="governance.hold",
            )
            raise HTTPException(
                status_code=423,
                detail={
                    "error": "Held for human approval",
                    "approval_ticket": ticket.id,
                    **explanation,
                },
            )

    blob_for_tokens = json.dumps(scrubbed_msgs, ensure_ascii=False)
    incr("tokens_scrubbed", float(max(1, len(blob_for_tokens) // 4)))

    payload = body.model_dump(mode="python", exclude_none=True)
    payload["messages"] = scrubbed_msgs

    client: httpx.AsyncClient = request.app.state.http_client
    response_headers = {
        CORR_HEADER: corr_id,
        RISK_HEADER: str(risk_score),
        "X-ShieldAI-Policy-Action": decision.action,
    }

    if body.stream:
        payload["stream"] = True
        accumulated: list[str] = []
        metadata: dict[str, Any] = {}

        async with client.stream(
            "POST",
            chat_completions_endpoint(settings.upstream_base_url),
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.upstream_api_key}",
                "Content-Type": "application/json",
            },
            timeout=settings.upstream_timeout_s,
        ) as resp:
            if resp.status_code >= 400:
                detail = await resp.aread()
                await vault.clear_key(vault_key)
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=detail.decode("utf-8", errors="replace")[:4096],
                )
            async for line in resp.aiter_lines():
                if not line:
                    continue
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    metadata.setdefault("id", obj.get("id", corr_id))
                    metadata.setdefault("model", obj.get("model", body.model))
                    for choice in obj.get("choices") or []:
                        delta = choice.get("delta") or {}
                        c = delta.get("content")
                        if c:
                            accumulated.append(str(c))

        full_text = "".join(accumulated)
        deanonymized = await deanonymize_text(
            full_text, vault=vault, vault_key=vault_key
        )
        await vault.clear_key(vault_key)

        await RateLimitChecker.account_response_tokens(x_shieldai_key, deanonymized)
        incr("relay_ok")

        sid = str(metadata.get("id", corr_id))
        model = str(metadata.get("model", body.model))
        return StreamingResponse(
            _sse_chunks(model=model, corr_id=sid, deanonymized=deanonymized),
            media_type="text/event-stream",
            headers=response_headers,
        )

    payload["stream"] = False
    try:
        resp = await post_chat_completion(
            client,
            base_url=settings.upstream_base_url,
            api_key=settings.upstream_api_key,
            payload=payload,
        )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=resp.status_code,
                detail=resp.text[:4096],
            )
        data = resp.json()
        restored = await _deanonymize_response(
            data, vault=vault, vault_key=vault_key
        )
        await RateLimitChecker.account_response_tokens(x_shieldai_key, restored)
        incr("relay_ok")
        return JSONResponse(content=data, headers=response_headers)
    finally:
        await vault.clear_key(vault_key)
