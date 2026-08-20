from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.core.presidio_setup import build_analyzer_engine
from app.core.settings import settings as global_settings
from app.proxy.compliance import compliance_report, load_policies
from app.proxy.config_store import load_config, merge_patch
from app.proxy.identity import TokenError, verify_jwt
from app.proxy.metrics import snapshot

router = APIRouter(tags=["internal"])


def verify_internal_token(
    request: Request,
    x_shield_internal_token: str | None = Header(
        default=None, alias="X-Shield-Internal-Token"
    ),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Accept a short-lived admin/analyst JWT; retain the legacy token for CLI use."""
    settings = getattr(request.app.state, "settings", global_settings)
    if authorization and authorization.lower().startswith("bearer "):
        try:
            claims = verify_jwt(
                authorization.split(" ", 1)[1].strip(),
                secret=settings.jwt_secret,
                issuer=settings.jwt_issuer,
            )
        except TokenError as exc:
            raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc
        if claims.get("role") not in {"admin", "analyst"}:
            raise HTTPException(status_code=403, detail="Administrator or analyst role required")
        return claims
    if x_shield_internal_token and x_shield_internal_token == settings.shield_internal_token:
        return {"sub": "internal-service", "role": "admin", "legacy": True}
    raise HTTPException(status_code=401, detail="Unauthorized")


def require_admin(
    claims: dict[str, Any] = Depends(verify_internal_token),
) -> dict[str, Any]:
    if claims.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator role required")
    return claims


@router.get("/metrics")
async def metrics(_: None = Depends(verify_internal_token)) -> dict[str, Any]:
    snap = snapshot()
    return {
        "pii_intercepted_total": snap.get("pii_intercepted", 0),
        "tokens_scrubbed_total": snap.get("tokens_scrubbed", 0),
        "active_threats_blocked_total": snap.get("threats_blocked", 0),
        "relay_success_total": snap.get("relay_ok", 0),
        "snapshot": snap,
    }


@router.get("/logs")
async def logs(
    request: Request,
    limit: int = 100,
    _: None = Depends(verify_internal_token),
) -> dict[str, Any]:
    return {"events": request.app.state.audit.recent(limit=limit)}


@router.get("/audit/verify")
async def audit_verify(
    request: Request,
    _: None = Depends(verify_internal_token),
) -> dict[str, Any]:
    """Recompute the SHA-256 hash chain and report whether it is intact."""
    return request.app.state.audit.verify_chain()


@router.get("/audit/export")
async def audit_export(
    request: Request,
    limit: int = 5000,
    _: None = Depends(verify_internal_token),
) -> dict[str, Any]:
    return {"events": request.app.state.audit.export_all(max_rows=limit)}


@router.get("/config")
async def get_config(_: None = Depends(verify_internal_token)) -> dict[str, Any]:
    return load_config(global_settings.config_store_path)


@router.patch("/config")
async def patch_config(
    request: Request,
    body: dict[str, Any],
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    cfg = merge_patch(global_settings.config_store_path, body)
    request.app.state.config = cfg
    request.app.state.analyzer = build_analyzer_engine(cfg)
    return cfg


@router.delete("/rate_limits")
async def reset_limits(_: None = Depends(verify_internal_token)) -> dict[str, str]:
    from app.proxy.rate_limit import RateLimitChecker

    RateLimitChecker._by_key.clear()
    return {"status": "ok"}


@router.get("/compliance/report")
async def get_compliance_report(
    request: Request,
    _: None = Depends(verify_internal_token),
) -> dict[str, Any]:
    """Regulatory control coverage (NRB, Privacy Act 2018, ISO 27001, NIST, OWASP)."""
    policies = getattr(request.app.state, "policies", {"rules": []})
    report = compliance_report(policies)
    report["vault_encryption_enabled"] = bool(
        getattr(request.app.state.vault, "encryption_enabled", False)
    )
    report["zero_trust_enabled"] = bool(global_settings.zero_trust_enabled)
    return report


@router.get("/policies")
async def get_policies(
    request: Request,
    _: None = Depends(verify_internal_token),
) -> dict[str, Any]:
    return getattr(request.app.state, "policies", load_policies(global_settings.policy_store_path))


@router.get("/approvals")
async def list_approvals(
    request: Request,
    pending_only: bool = True,
    _: None = Depends(verify_internal_token),
) -> dict[str, Any]:
    queue = request.app.state.approvals
    items = queue.pending() if pending_only else queue.all()
    return {"approvals": items}


@router.get("/correlations")
async def get_correlations(
    request: Request,
    _: None = Depends(verify_internal_token),
) -> dict[str, Any]:
    """Cross-request security correlation incidents (bursts, escalation)."""
    return request.app.state.correlator.summary()


@router.get("/siem/export")
async def siem_export(
    request: Request,
    fmt: str = "cef",
    limit: int = 1000,
    forward: bool = False,
    _: None = Depends(verify_internal_token),
) -> Any:
    """Export audit events as CEF (or JSON), optionally forwarding to a SIEM."""
    from fastapi.responses import PlainTextResponse

    from app.proxy.siem import events_to_cef, forward_to_siem

    events = request.app.state.audit.recent(limit=limit)
    result: dict[str, Any] = {"count": len(events)}

    if forward and global_settings.siem_webhook_url:
        client = request.app.state.http_client
        result["forward"] = await forward_to_siem(
            client, global_settings.siem_webhook_url, events, fmt=fmt
        )

    if fmt == "json":
        return {"events": events, **result}
    return PlainTextResponse(events_to_cef(events), media_type="text/plain")


@router.post("/approvals/{ticket_id}/decide")
async def decide_approval(
    request: Request,
    ticket_id: str,
    body: dict[str, Any],
    claims: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    approve = bool(body.get("approve", False))
    approver = str(claims.get("sub", "admin"))
    ticket = request.app.state.approvals.decide(
        ticket_id, approver=approver, approve=approve
    )
    if ticket is None:
        raise HTTPException(status_code=404, detail="Unknown approval ticket")
    return ticket.to_dict()


@router.get("/alerts")
async def alerts(
    request: Request,
    since: float = 0,
    _: None = Depends(verify_internal_token),
) -> dict[str, Any]:
    return {"alerts": request.app.state.alert_ring.pull_since(since)}


@router.get("/debug/prompt/{correlation_id}")
async def debug_prompt_slice(
    request: Request,
    correlation_id: str,
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, str]:
    if not global_settings.prompt_debug_enabled:
        raise HTTPException(status_code=404, detail="Prompt debugging is disabled")
    row = request.app.state.prompt_debug.get(correlation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Debug snapshot expired or unknown id")
    return row


@router.get("/system/status")
async def system_status(
    request: Request,
    _: dict[str, Any] = Depends(verify_internal_token),
) -> dict[str, Any]:
    settings = request.app.state.settings
    audit = request.app.state.audit.verify_chain()
    return {
        "service": "shieldai",
        "ready": all(
            hasattr(request.app.state, name)
            for name in ("analyzer", "vault", "audit", "users", "policies", "http_client")
        ),
        "nlp_engine_requested": settings.nlp_engine,
        "upstream_configured": bool(settings.upstream_base_url),
        "upstream_host": settings.upstream_base_url.split("/v1", 1)[0],
        "audit_chain_ok": bool(audit.get("ok")),
        "zero_trust_enabled": settings.zero_trust_enabled,
        "mfa_enabled": settings.mfa_enabled,
        "vault_encryption_enabled": bool(getattr(request.app.state.vault, "encryption_enabled", False)),
        "prompt_debug_enabled": settings.prompt_debug_enabled,
        "siem_configured": bool(settings.siem_webhook_url),
    }


@router.get("/users")
async def list_users(
    request: Request,
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    return {"users": request.app.state.users.list_users()}


@router.post("/users", status_code=201)
async def create_user(
    request: Request,
    body: dict[str, Any],
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))
    role = str(body.get("role", "teller"))
    if len(username) < 3 or len(password) < 8:
        raise HTTPException(status_code=422, detail="Username must be 3+ characters and password 8+")
    try:
        created = request.app.state.users.create_user(username, password, role)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not created:
        raise HTTPException(status_code=409, detail="User already exists")
    return request.app.state.users.get(username).__dict__ | {"password_hash": "[redacted]", "totp_secret": None}


@router.patch("/users/{username}")
async def update_user(
    request: Request,
    username: str,
    body: dict[str, Any],
    claims: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    if username == claims.get("sub") and body.get("disabled") is True:
        raise HTTPException(status_code=409, detail="You cannot disable your own account")
    try:
        changed = request.app.state.users.update_user(
            username,
            role=body.get("role"),
            disabled=body.get("disabled"),
            password=body.get("password"),
            reset_mfa=bool(body.get("reset_mfa", False)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not changed:
        raise HTTPException(status_code=404, detail="User not found")
    return next(u for u in request.app.state.users.list_users() if u["username"] == username)
