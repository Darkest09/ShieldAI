from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import html

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.presidio_setup import build_analyzer_engine
from app.core.settings import settings as global_settings
from app.core.vault import build_vault
from app.proxy.audit import AuditLog
from app.proxy.compliance import load_policies
from app.proxy.config_store import load_config
from app.proxy.correlation import CorrelationEngine
from app.proxy.governance import ApprovalQueue
from app.proxy.identity import UserStore
from app.proxy.metrics import configure_persistence
from app.proxy.metrics_internal import router as internal_router
from app.proxy.routes_auth import router as auth_router
from app.proxy.routes_chat import router as chat_router
from app.proxy.signals import AlertRing, PromptDebugBuffer


import logging

_log = logging.getLogger("shieldai")


def _emit_hardening_warnings(settings) -> None:
    """Warn loudly about insecure defaults at startup (production hygiene)."""
    warnings: list[str] = []
    if settings.shield_internal_token == "dev-internal":
        warnings.append("SHIELD_INTERNAL_TOKEN is the default - set a strong value.")
    if settings.jwt_secret == "dev-jwt-secret-change-me" and settings.zero_trust_enabled:
        warnings.append("JWT_SECRET is the default while Zero-Trust is ON - rotate it.")
    if settings.zero_trust_enabled and not settings.vault_encryption_key:
        warnings.append("Zero-Trust is ON but VAULT_ENCRYPTION_KEY is unset (PII at rest is plaintext).")
    if not settings.allowed_shield_keys() and not settings.zero_trust_enabled:
        warnings.append("Proxy is OPEN (no SHIELD_API_KEYS, Zero-Trust off) - fine for demos only.")
    for w in warnings:
        _log.warning("[hardening] %s", w)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = global_settings
    cfg = load_config(global_settings.config_store_path)
    app.state.config = cfg
    app.state.analyzer = build_analyzer_engine(cfg)
    app.state.vault = build_vault(global_settings)
    app.state.audit = AuditLog(global_settings.audit_sqlite_path)
    app.state.alert_ring = AlertRing()
    app.state.prompt_debug = PromptDebugBuffer()
    app.state.users = UserStore(global_settings.users_store_path)
    app.state.policies = load_policies(global_settings.policy_store_path)
    app.state.approvals = ApprovalQueue(store_path=global_settings.approvals_store_path)
    app.state.correlator = CorrelationEngine()
    configure_persistence(global_settings.metrics_store_path)
    _emit_hardening_warnings(global_settings)

    timeout = global_settings.upstream_timeout_s
    async with httpx.AsyncClient(timeout=timeout) as client:
        app.state.http_client = client
        yield


def create_app() -> FastAPI:
    origins = [
        o.strip() for o in global_settings.dashboard_origins.split(",") if o.strip()
    ]
    if global_settings.extra_cors_origins.strip():
        origins.extend(
            o.strip()
            for o in global_settings.extra_cors_origins.split(",")
            if o.strip()
        )
    origins = list(dict.fromkeys(origins))
    app = FastAPI(
        title="ShieldAI",
        description=(
            "ShieldAI — Privacy-Preserving AI Gateway (PPAG) on Zero-Trust principles. "
            "Prompt inspection, PII anonymisation, AES-256 vault, Zero-Trust access "
            "control, compliance policy enforcement (NRB / Individual Privacy Act 2018 / "
            "ISO 27001 / NIST 800-207 / OWASP-LLM), tamper-evident audit, and human "
            "approval workflows. Not a legal compliance certification."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", include_in_schema=True)
    async def health() -> dict[str, str]:
        """Liveness probe for Docker / load balancers (no auth)."""
        return {"status": "ok", "service": "shieldai"}

    @app.get("/ready", include_in_schema=True)
    async def ready() -> dict[str, object]:
        """Readiness probe: core processing dependencies were initialized."""
        components = {
            name: hasattr(app.state, name)
            for name in ("analyzer", "vault", "audit", "users", "policies", "http_client")
        }
        return {"status": "ready" if all(components.values()) else "not_ready", "components": components}

    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(internal_router, prefix="/internal")

    _static = Path(__file__).resolve().parent / "static"
    _chat_html = _static / "chat.html"
    _dashboard_dist = Path(__file__).resolve().parents[1] / "dashboard" / "dist"

    if global_settings.dashboard_enabled and (_dashboard_dist / "index.html").is_file():
        assets_dir = _dashboard_dist / "assets"
        if assets_dir.is_dir():
            app.mount("/dashboard/assets", StaticFiles(directory=assets_dir), name="dashboard-assets")

        @app.get("/dashboard", include_in_schema=False)
        async def dashboard_redirect() -> RedirectResponse:
            return RedirectResponse("/dashboard/", status_code=307)

        @app.get("/dashboard/{path:path}", include_in_schema=False)
        async def dashboard(path: str = "") -> FileResponse:
            candidate = (_dashboard_dist / path).resolve()
            if path and candidate.is_file() and _dashboard_dist.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(_dashboard_dist / "index.html")

    if global_settings.demo_chat_enabled and _chat_html.is_file():

        @app.get("/chat", include_in_schema=False)
        async def demo_chat_page() -> HTMLResponse:
            raw = _chat_html.read_text(encoding="utf-8")
            body = raw.replace(
                "{{DEFAULT_MODEL}}",
                html.escape(global_settings.demo_chat_default_model, quote=True),
            )
            return HTMLResponse(
                body,
                media_type="text/html; charset=utf-8",
                headers={"Cache-Control": "no-store"},
            )

        @app.get("/chat.html", include_in_schema=False)
        async def demo_chat_page_alias() -> RedirectResponse:
            return RedirectResponse("/chat", status_code=302)

        @app.get("/", include_in_schema=False)
        async def root_to_demo_chat() -> RedirectResponse:
            return RedirectResponse("/chat", status_code=302)
    elif global_settings.demo_chat_enabled:

        @app.get("/chat", include_in_schema=False)
        async def demo_chat_missing() -> HTMLResponse:
            return HTMLResponse(
                "<p>Demo chat UI file missing. Reinstall the <code>app/proxy/static/chat.html</code> asset.</p>",
                status_code=500,
            )

    return app


app = create_app()
