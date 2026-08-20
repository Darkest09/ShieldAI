# Proposal → Implementation Traceability

Maps every component of the proposal **"Privacy-Preserving AI Gateway (PPAG)
based on Zero-Trust principles for Class 'A' commercial banks in Kathmandu"** to
the code that implements it. Status: ✅ implemented · ◐ partial · ⚙ configurable.

## System Architecture (Proposal §11)

| Proposed layer / component | Status | Where |
|---|---|---|
| **Identity & Access Verification** | | |
| Multi-factor authentication (TOTP) | ✅ | enroll/verify flow `/v1/auth/mfa/*`; otpauth QR URI; `MFA_ENABLED` |
| Role-based access control (RBAC) | ✅ | [identity.py](app/proxy/identity.py) `ROLE_MAX_TIER` (admin/analyst/officer/teller) |
| JWT auth (OAuth2 password grant) | ✅ | [routes_auth.py](app/proxy/routes_auth.py) accepts JSON + form `grant_type=password` |
| Context-aware policy + device posture | ✅ | `_resolve_principal` + `score_request_risk` + `X-Device-Trusted` gate |
| Device verification | ◐→✅ | header-based device id/trust binding; `REQUIRE_TRUSTED_DEVICE` holds untrusted high-risk |
| **Prompt Inspection Engine** | | |
| Real-time prompt scanning | ✅ | [preflight.py](app/proxy/preflight.py) |
| Regex-based PII detection | ✅ | [recognizers_custom.py](app/proxy/recognizers_custom.py) |
| NLP-based sensitive classification | ✅ | Presidio + spaCy `en_core_web_lg` ([presidio_setup.py](app/core/presidio_setup.py)) |
| Prompt-injection attack detection | ✅ | [injection.py](app/proxy/injection.py) |
| **Privacy Preservation Layer** | | |
| Data masking / anonymisation | ✅ | [strategies.py](app/proxy/strategies.py), [preflight.py](app/proxy/preflight.py) |
| Tokenisation of customer identifiers | ✅ | reversible vault tokens |
| Encryption of AI requests/responses | ✅ | TLS via httpx; **AES-256-GCM** vault at rest ([encryption.py](app/core/encryption.py)) ⚙ key |
| Secure temporary memory handling | ✅ | [vault.py](app/core/vault.py) TTL + `clear_key` per request |
| **Compliance Enforcement Module** | | |
| NRB / Privacy Act / ISO / NIST mapping | ✅ | [compliance.py](app/proxy/compliance.py) `CONTROL_CATALOGUE` |
| Policy-based blocking rules | ✅ | `evaluate_policies` (block/hold/warn/redact) |
| Audit trail generation | ✅ | [audit.py](app/proxy/audit.py) hash chain |
| **Monitoring & Logging Layer** | | |
| Immutable audit logging | ✅ | SHA-256 hash-chained SQLite + `/internal/audit/verify` |
| AI interaction monitoring | ✅ | [metrics.py](app/proxy/metrics.py) (persisted), `/internal/logs` |
| Suspicious behaviour detection | ✅ | injection heuristics + context risk score |
| Security event correlation | ✅ | [correlation.py](app/proxy/correlation.py) `/internal/correlations` (bursts, escalation) |
| SIEM integration | ✅ | [siem.py](app/proxy/siem.py) CEF export + forward `/internal/siem/export` |
| **Explainability & Governance Layer** | | |
| Transparent policy explanations | ✅ | [governance.py](app/proxy/governance.py) `build_user_explanation` (returned to user) |
| User risk notifications | ✅ | `X-ShieldAI-Risk-Score` header + alert ring |
| Compliance reporting dashboards | ✅ | Dashboard **Governance** tab ([Governance.tsx](app/dashboard/src/pages/Governance.tsx)) |
| Human approval workflow (high-risk) | ✅ | `ApprovalQueue` + `/internal/approvals` + 423-hold flow |

## Theoretical Foundations (§3)
- **Zero-Trust ("never trust, always verify")** — every request re-verifies token,
  role, and context risk before reaching an AI provider (`_resolve_principal`,
  `score_request_risk`). `NIST-800-207` controls in the catalogue.
- **Privacy-by-Design / data minimisation** — tool payloads redacted, vault TTL,
  shadow mode, encryption-at-rest. `IPA-2018-S5`.
- **Human factors / insider risk** — RBAC + per-role risk weighting + approval gate.

## Hypotheses (§8) — how they are measured
- **H1 (≥70% leakage reduction, detection accuracy)** — [scripts/evaluate.py](scripts/evaluate.py)
  reports precision/recall/F1 + false-negative/positive rates on a labelled
  synthetic banking dataset ([scripts/generate_synthetic_dataset.py](scripts/generate_synthetic_dataset.py)).
- **H2 (compliance + usability)** — `/internal/compliance/report` quantifies
  control coverage; latency captured by the evaluation harness; explanations +
  approval workflow provide the usability/oversight evidence.

## Tools & Technologies (§14)

| Proposed | Status | Notes |
|---|---|---|
| Python 3.11, FastAPI, REST | ✅ | |
| Open-source LLMs | ✅ | any OpenAI-compatible upstream (Ollama, vLLM, …) |
| spaCy NLP | ✅ | Presidio NER (default, ~6ms) |
| Hugging Face Transformers | ✅ | optional NER backend `NLP_ENGINE=transformers` ([presidio_setup.py](app/core/presidio_setup.py)); 100% recall vs spaCy 95% |
| OAuth2 / JWT | ✅ | HS256 JWT (stdlib) + OAuth2 password-grant form |
| AES-256 encryption | ✅ | AES-256-GCM vault (`cryptography`) |
| TLS | ✅ | httpx; terminate at reverse proxy in prod |
| Regex + NLP DLP | ✅ | custom recognizers + Presidio (score threshold tuned) |
| Docker | ✅ | Dockerfile + compose |
| OWASP-LLM testing | ✅ | expanded injection patterns (8 rules) + `OWASP-LLM01/06` controls |
| Elasticsearch / Kibana / SIEM | ✅ | CEF export + webhook forward to any SIEM collector |
| Simulated banking dataset | ✅ | synthetic generator (no real customer data) |

## Endpoints added for the PPAG features
- `POST /v1/auth/token` (JSON or OAuth2 form) · `GET /v1/auth/me` — login / introspection.
- `POST /v1/auth/mfa/enroll` · `POST /v1/auth/mfa/verify` — TOTP MFA enrollment.
- `GET /internal/compliance/report` — regulatory coverage.
- `GET /internal/policies` — active policy rules.
- `GET /internal/approvals` · `POST /internal/approvals/{id}/decide` — governance.
- `GET /internal/correlations` — cross-request security correlation incidents.
- `GET /internal/siem/export?fmt=cef&forward=true` — SIEM export / forward.
- `GET /internal/audit/verify` — tamper-evidence check.

## Honest limitations
- "Immutable" audit = tamper-**evident** (hash chain), not write-once storage.
- Device "posture" is header-asserted (`X-Device-Trusted`), not hardware-attested —
  real attestation needs a device-management agent (out of scope).
- Hugging Face Transformers now wired in as an optional backend
  (`NLP_ENGINE=transformers`, `dslim/bert-base-NER`): 100% recall / 100% privacy
  coverage vs spaCy's 95%, at ~42ms vs ~6ms. spaCy remains the latency-friendly
  default; transformers is opt-in.
- Correlation engine + alert ring are in-memory (window-bounded); approvals and
  metrics now persist to disk. For multi-instance prod, back them with a shared store.
