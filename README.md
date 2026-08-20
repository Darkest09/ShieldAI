# ShieldAI — Privacy-Preserving AI Gateway (PPAG)

A zero-trust privacy gateway that sits between users and any OpenAI-compatible LLM. ShieldAI inspects every prompt for PII and prompt-injection attempts, anonymises sensitive data before it leaves your boundary, optionally encrypts it at rest in a time-limited vault, enforces compliance policy, and keeps a tamper-evident audit trail — all exposed behind a FastAPI service with a React management dashboard.

Built for the BSc (Hons) Ethical Hacking & Cybersecurity programme at Softwarica College of IT & E-Commerce (Coventry University).

## Features

- **Zero-Trust access control** — JWT authentication (`POST /v1/auth/token`), RBAC roles, and per-request context risk scoring. Enable with `ZERO_TRUST_ENABLED=true`.
- **PII detection & anonymisation** — Hugging Face transformer NER backend (100% recall on the evaluation set) with automatic fallback to a fast spaCy engine. PII is tokenised with placeholder/mask/hash strategies before it is sent upstream.
- **Reversible privacy vault** — tokenised values can be recovered within a TTL window, with optional **AES-256-GCM** encryption at rest (`VAULT_ENCRYPTION_KEY`).
- **Prompt-injection defence** — heuristic and semantic injection scanning with configurable `block` / `warn` policies.
- **Compliance policy engine** — policy actions (block / hold / warn / redact) mapped to NRB Cyber Resilience, Individual Privacy Act 2018, ISO 27001, NIST 800-207, and OWASP LLM Top 10. Coverage report at `GET /internal/compliance/report` and the dashboard's Governance tab.
- **Human-in-the-loop governance** — high-risk prompts are held in an approval queue for review before release (`/internal/approvals`).
- **Audited, tamper-evident trail** — every request is written to a SQLite audit log with a verifiable hash chain; optional SIEM webhook forwarding (CEF).
- **Rate limiting & token budgeting** — per-key request rate limits and token budgets with Redis-backed distributed counters when available.
- **Evaluation harness** — synthetic Nepali-banking dataset generator and evaluator producing precision/recall/F1, false positives/negatives, and latency metrics.
- **Browser demo chat** — a lightweight chat UI served at `/chat` so reviewers can try prompts without a terminal.

## Architecture

```
┌────────────┐    X-ShieldAI-Key / Bearer JWT     ┌──────────────────────────┐
│  Client /  │ ───────────────────────────────────► │   ShieldAI FastAPI proxy │
│  Dashboard │                                     │  (app/proxy)             │
└────────────┘                                     │  preflight → PII scrub   │
                                                   │  → injection scan → vault│
                                                   │  → policy → governance   │
                                                   │  → upstream → postflight │
                                                   │  → audit chain            │
                                                   └────────────┬─────────────┘
                                                                │ OpenAI-compatible
                                                   ┌────────────▼─────────────┐
                                                   │ Upstream LLM (OpenAI,    │
                                                   │ Groq, Ollama, vLLM, ...) │
                                                   └──────────────────────────┘
```

## Tech stack

- **Backend** — Python 3.11+, FastAPI, Uvicorn, Pydantic settings
- **Privacy / NLP** — Presidio Analyzer/Anonymizer, Hugging Face Transformers, spaCy, tiktoken
- **Security** — PyJWT, TOTP (MFA), cryptography (AES-256-GCM), Redis (optional)
- **Dashboard** — React 18, TypeScript, Vite, Tailwind CSS
- **Deployment** — Docker + Docker Compose (single container, optional Redis service)

## Quick start

### Option A — Local (venv + npm)

Prerequisites: Python 3.11+, Node.js 18+.

1. Clone the repository and open a terminal in the project root.

2. Create a virtual environment and install the project:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -e ".[dev]"
   ```

3. Configure environment variables (see [Configuration](#configuration)):

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

   At minimum set `UPSTREAM_BASE_URL` and `UPSTREAM_API_KEY` (use `ollama` as the key for a local Ollama server).

4. Build and serve the dashboard (in a second terminal):

   ```powershell
   cd app\dashboard
   npm install
   npm run dev
   ```

5. Start the API:

   ```powershell
   python -m uvicorn app.proxy.main:app --host 127.0.0.1 --port 8888
   ```

6. Open the demo chat at <http://127.0.0.1:8888/chat> or the dashboard at <http://localhost:5173>.

7. Run the test suite:

   ```powershell
   pytest
   ```

### Option B — Docker

Prerequisites: Docker Desktop.

1. Copy and configure `.env`:

   ```bash
   cp .env.example .env
   ```

2. Build and start:

   ```bash
   docker compose up --build
   ```

3. Open the demo chat at <http://127.0.0.1:8888/chat> and the health check at <http://127.0.0.1:8888/health>.

### Option C — Windows one-click launcher

Double-click `ShieldAI.cmd` (or run `ShieldAI-Launcher.ps1`) for a control panel that installs dependencies, starts/stops the API and dashboard, opens the demo pages, verifies the audit chain, and runs the test suite.

## Configuration

Configuration is read from the environment or a `.env` file (see `.env.example` for the full list with comments). Key variables:

| Variable | Default | Description |
| --- | --- | --- |
| `UPSTREAM_BASE_URL` | `https://api.openai.com/v1` | Any OpenAI-compatible API base URL (Groq, Ollama, vLLM, OpenRouter...). |
| `UPSTREAM_API_KEY` | *(empty)* | Upstream provider key (`ollama` works for local Ollama). |
| `SHIELD_INTERNAL_TOKEN` | `dev-internal` | Internal token for `/internal/*` endpoints — set a strong value in production. |
| `SHIELD_API_KEYS` | *(empty)* | Comma-separated client keys accepted via `X-ShieldAI-Key`. Empty = open proxy (demos only). |
| `ZERO_TRUST_ENABLED` | `false` | Require a valid JWT on every request and enforce RBAC. |
| `JWT_SECRET` | `dev-jwt-secret-change-me` | HS256 signing secret — rotate in production. |
| `VAULT_ENCRYPTION_KEY` | *(empty)* | Base64 32-byte key for AES-256-GCM vault encryption. Empty = in-memory plaintext (TTL-bounded). |
| `NLP_ENGINE` | `transformers` | PII backend: `transformers` (heavy, highest recall) or `spacy` (fast). |
| `INJECTION_POLICY` | `block` | `block` or `warn` on detected prompt-injection attempts. |
| `DEMO_CHAT_ENABLED` | `true` | Serve the browser demo chat at `/chat`. Disable on public servers. |

> **Production checklist** — set strong `SHIELD_INTERNAL_TOKEN` / `JWT_SECRET` / `SHIELD_API_KEYS`, enable `ZERO_TRUST_ENABLED=true`, set a real `VAULT_ENCRYPTION_KEY`, and set `DEMO_CHAT_ENABLED=false`.

## API endpoints

- `GET /health` — liveness probe
- `GET /ready` — readiness probe (dependency check)
- `POST /v1/auth/token` — issue a JWT (Zero-Trust login)
- `POST /v1/chat/completions` — OpenAI-compatible chat endpoint (PII-scrubbed upstream proxy)
- `GET /chat` — browser demo chat UI
- `GET /dashboard/` — management dashboard (requires a built `dist` bundle)
- `GET /internal/health` — internal health detail
- `GET /internal/compliance/report` — compliance coverage report
- `GET /internal/audit` — audit log with hash-chain verification
- `GET /internal/approvals` — human-approval queue for held prompts
- `GET /internal/metrics` — request/performance metrics
- `POST /internal/siem/export` — forward audit events to a SIEM webhook

Interactive API docs are served by FastAPI at <http://127.0.0.1:8888/docs>.

## Project structure

```
app/
  core/       # Settings, encryption, vault, Presidio engine, SPA cache
  proxy/      # FastAPI app, auth, chat, compliance, governance, SIEM, metrics
  dashboard/  # React + TypeScript management dashboard (Vite)
scripts/      # Dev helpers, evaluation harness, user management, smoke tests
tests/        # API, compliance, SIEM, governance, encryption, injection tests
Dockerfile    # Single-container build (API + built dashboard)
docker-compose.yml
pyproject.toml   # Package metadata, dependencies, pytest config
.env.example     # Configuration template (copy to .env)
```

## Development

```powershell
scripts\dev.ps1                 # Start backend + dashboard for development
scripts\smoke-test.ps1          # Quick end-to-end smoke test
scripts\generate_synthetic_dataset.py   # Build the labelled evaluation dataset
scripts\evaluate.py            # Run PII evaluation (precision/recall/F1, latency)
scripts\manage_users.py        # Manage Zero-Trust users and roles
```

Run the full test suite with `pytest`. Install the optional heavy NLP backend with `pip install -e ".[transformers]"`.

## Security & disclaimer

ShieldAI is an academic demonstration of privacy-preserving AI gateway concepts. It is not a substitute for a formal compliance certification. Threat models, policy mappings, and NER models should be reviewed and validated for your environment before production use.