from enum import StrEnum

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class InjectionPolicy(StrEnum):
    block = "block"
    warn = "warn"


class AnonymizationStrategy(StrEnum):
    placeholder = "placeholder"
    mask = "mask"
    hash = "hash"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # OpenAI-compatible upstream (OpenAI, Groq, Ollama, vLLM, OpenRouter, etc.)
    upstream_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("UPSTREAM_BASE_URL", "OPENAI_BASE_URL"),
    )
    upstream_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "UPSTREAM_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY"
        ),
    )
    shield_internal_token: str = "dev-internal"
    shield_api_keys: str = Field(
        default="",
        validation_alias=AliasChoices("SHIELD_API_KEYS", "SHIELD_API_KEY"),
        description=(
            "Comma-separated allowlist of client Shield keys accepted on "
            "/v1/chat/completions via the X-ShieldAI-Key header. When empty, "
            "the proxy is open (anonymous) — set this in production."
        ),
    )
    dashboard_origins: str = "http://localhost:5173"
    vault_ttl_seconds: int = 900
    injection_policy: InjectionPolicy = InjectionPolicy.block
    audit_sqlite_path: str = "./data/shieldai_audit.db"
    upstream_timeout_s: float = 120.0
    redis_url: str | None = None
    token_budget_per_key: int = 200_000
    rate_limit_rpm: int = 120
    anon_strategy: AnonymizationStrategy = AnonymizationStrategy.placeholder
    hash_salt: str = "shieldai-v1"
    config_store_path: str = "./data/shieldai_config.json"
    nlp_engine: str = Field(
        default="transformers",
        description=(
            "PII NER backend: 'transformers' (Hugging Face, primary — 100% recall) "
            "or 'spacy' (fast, ~6ms). Transformers needs torch + transformers + "
            "spacy-huggingface-pipelines; if missing it auto-falls back to spaCy."
        ),
    )
    transformers_model: str = Field(
        default="dslim/bert-base-NER",
        description="Hugging Face token-classification model used when nlp_engine=transformers.",
    )
    shadow_mode: bool = Field(
        default=False,
        description="When True, observability only — no placeholders sent upstream.",
    )
    demo_chat_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("DEMO_CHAT_ENABLED", "SHIELD_DEMO_CHAT"),
        description="Serve a minimal browser chat UI at /chat for demos and grading.",
    )
    demo_chat_default_model: str = Field(
        default="openai/gpt-oss-120b",
        validation_alias=AliasChoices("DEMO_CHAT_DEFAULT_MODEL", "DEMO_CHAT_MODEL"),
        description="Default upstream model id in the demo chat UI.",
    )
    dashboard_enabled: bool = Field(
        default=True,
        description="Serve the built React dashboard from /dashboard when dist assets exist.",
    )
    prompt_debug_enabled: bool = Field(
        default=False,
        description="Retain short-lived before/after prompt snapshots for admin debugging.",
    )
    extra_cors_origins: str = Field(
        default="",
        validation_alias=AliasChoices("EXTRA_CORS_ORIGINS", "SHIELD_EXTRA_CORS_ORIGINS"),
        description="Comma-separated extra browser origins for CORS (e.g. another local chat UI).",
    )

    # --- Zero-Trust identity & access (PPAG) ---------------------------------
    zero_trust_enabled: bool = Field(
        default=False,
        description=(
            "When True, every /v1 request must carry a valid Bearer JWT issued "
            "by /v1/auth/token; role + context risk are enforced per request "
            "('never trust, always verify'). Off by default so the demo works."
        ),
    )
    jwt_secret: str = Field(
        default="dev-jwt-secret-change-me",
        description="HS256 signing secret for access tokens. Rotate in production.",
    )
    jwt_issuer: str = "shieldai-ppag"
    jwt_ttl_seconds: int = 3600
    users_store_path: str = "./data/shieldai_users.json"
    mfa_enabled: bool = Field(
        default=False,
        description="Require a TOTP code at login for users that have MFA enrolled.",
    )

    # --- Compliance & governance ---------------------------------------------
    policy_store_path: str = "./data/shieldai_policies.json"
    approvals_store_path: str = "./data/shieldai_approvals.json"
    metrics_store_path: str = "./data/shieldai_metrics.json"
    approval_required_tier: str = Field(
        default="critical",
        description=(
            "Semantic risk tier at/above which a prompt is held for human "
            "approval (governance workflow) when zero_trust is enabled."
        ),
    )
    require_trusted_device: bool = Field(
        default=False,
        description=(
            "When True (and Zero-Trust on), high/critical-tier prompts from a "
            "device that does not present X-Device-Trusted: true are held."
        ),
    )
    siem_webhook_url: str = Field(
        default="",
        description="Optional SIEM HTTP collector URL to forward audit events (CEF).",
    )

    # --- Privacy preservation: vault encryption at rest ----------------------
    vault_encryption_key: str = Field(
        default="",
        description=(
            "Base64 32-byte key enabling AES-256-GCM encryption of vaulted PII. "
            "Requires the 'cryptography' package. Empty == in-memory plaintext "
            "(still TTL-bounded), preserving zero-dependency local runs."
        ),
    )

    def allowed_shield_keys(self) -> frozenset[str]:
        """Parsed allowlist of client Shield keys (empty == proxy is open)."""
        return frozenset(
            k.strip() for k in self.shield_api_keys.split(",") if k.strip()
        )


settings = Settings()
