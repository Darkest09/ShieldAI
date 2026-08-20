# Context file for report writing — give this entire file to your AI

## What this is
You are helping write a **thesis report** for a university student. This file contains everything the AI needs to know: the thesis title, proposal content, what the software does, how it is built, and what each part of the codebase does. Do not invent features that are not listed here.

---

## Thesis title (exact)
Design and Development of a Privacy-Preserving AI Gateway for Class 'A' Commercial Banks in Kathmandu: A Zero-Trust Framework for Mitigating PII Leakage and Ensuring Compliance with NRB Cyber Resilience Guidelines and the Individual Privacy Act (2018)

---

## What the project is
A working software prototype called **ShieldAI** — a privacy-preserving API gateway that sits between bank staff tools (or any client) and external large language model (LLM) providers such as OpenAI or Groq. Instead of prompts going directly to the LLM cloud, they go through this gateway first. The gateway detects and removes sensitive personally identifiable information (PII) before forwarding the request, then restores the original values in the response. Everything is logged in a tamper-evident audit trail. An operator dashboard shows metrics and logs.

The prototype is built with Python (FastAPI), Microsoft Presidio, spaCy, React, and SQLite. It runs locally on port 8888.

---

## Problem being solved
Class 'A' commercial banks in Kathmandu, Nepal are starting to use LLM tools (AI assistants, chatbots, productivity tools). When staff type prompts, they may accidentally include customer names, account numbers, citizenship numbers, phone numbers, or credentials. Those prompts go to external cloud LLM providers unfiltered. This creates:
1. Data leakage risk — sensitive data leaves the bank's control
2. Regulatory exposure — potential violations of Nepal Rastra Bank (NRB) Cyber Resilience Guidelines and the Individual Privacy Act 2018
3. Audit gaps — no record of what was sent

---

## Research objectives
1. Design a privacy-preserving AI gateway that intercepts LLM API traffic and enforces PII scrubbing before upstream transmission
2. Implement zero-trust principles on the AI egress channel: treat the external model and network as untrusted; minimize every payload
3. Incorporate Nepal-specific PII recognizers (citizenship numbers, mobile patterns) alongside general financial/credential patterns
4. Build a tamper-evident audit trail and operator dashboard for accountability and monitoring
5. Evaluate through synthetic test scenarios inspired by Class 'A' bank use cases in Kathmandu
6. Map implemented controls to NRB Cyber Resilience Guidelines and Individual Privacy Act (2018) principles

---

## Research questions
1. How can a proxy gateway architecture enforce data minimization for LLM traffic in a financial institution?
2. What PII entity types are most relevant to Nepali banking contexts, and how can they be reliably detected?
3. How does inserting a privacy gateway affect latency, usability, and LLM response quality?
4. To what extent do the implemented technical controls align with NRB and Privacy Act requirements?

---

## Architecture (how it works, step by step)

```
Bank Client (staff tool / browser / API consumer)
         |
         | HTTP POST /v1/chat/completions  (OpenAI-compatible format)
         v
+----------------------------------------------+
|            ShieldAI Gateway (FastAPI)         |
|  Port 8888                                    |
|                                               |
|  Step 1: Injection scan                       |
|           Heuristics check for prompt         |
|           injection attempts. If policy=block |
|           and injection found → 422 error.    |
|                                               |
|  Step 2: PII analysis (Presidio + spaCy)      |
|           Each message content is analyzed.  |
|           Detected spans are listed.          |
|                                               |
|  Step 3: Anonymize (vault)                    |
|           Detected spans are replaced with    |
|           tokens e.g. <PERSON_1>, stored in  |
|           a per-request vault with TTL.       |
|                                               |
|  Step 4: Forward to upstream LLM              |
|           The cleaned request is sent to      |
|           the configured external LLM API.    |
|                                               |
|  Step 5: De-anonymize response                |
|           The LLM reply is scanned for vault  |
|           tokens; originals are restored.     |
|           Vault entry is discarded after TTL. |
|                                               |
|  Step 6: Audit log                            |
|           Event written to SQLite with a      |
|           SHA-256 hash chain (tamper-evident).|
|           No raw PII is stored in the audit.  |
+----------------------------------------------+
         |
         v
External LLM provider (OpenAI / Groq / Ollama / etc.)
```

---

## Key components and where they live in the code

| Component | File(s) | What it does |
|-----------|---------|--------------|
| Gateway entry point | `app/proxy/main.py` | Creates FastAPI app, wires CORS, lifespan (startup: loads config, builds Presidio engine, vault, audit log, HTTP client), registers routes. Also serves `/health`, `/chat` demo UI, `/` redirect. |
| Chat route (main logic) | `app/proxy/routes_chat.py` | Handles `POST /v1/chat/completions`. Calls injection scan, rate limiter, Presidio scrub, upstream forward, de-anonymize, audit log, metrics. Returns OpenAI-format JSON or SSE stream. |
| PII detection + scrub | `app/proxy/preflight.py` | `scrub_text()` and `scrub_request_messages()`: run Presidio analysis on each message, replace detected spans with vault tokens. Uses `asyncio.to_thread` so Presidio doesn't block the event loop. |
| Response de-anonymize | `app/proxy/postflight.py` | Scans LLM response text for vault tokens, swaps them back to originals. |
| Presidio engine setup | `app/core/presidio_setup.py` | `build_analyzer_engine()`: loads spaCy model, loads Presidio built-in recognizers, disables any turned off in config, adds custom Nepal/credential recognizers. |
| Nepal + credential recognizers | `app/proxy/recognizers_custom.py` | Custom `PatternRecognizer` classes: `NP_CITIZENSHIP_NUMBER` (XX-XX-XX-XXXXX format), `NP_MOBILE_NUMBER` (Ncell/NTC 97x/98x patterns, +977 prefix), `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `STRIPE_API_KEY`. |
| Vault (token storage) | `app/core/vault.py` | In-memory dict vault with TTL per request. Stores `token → original_value` mappings. Redis-ready interface. |
| Audit log | `app/proxy/audit.py` | Append-only SQLite table. Each row stores: timestamp, correlation ID, risk level, entity type counts (not raw text), previous row hash, current row hash — forming a SHA-256 hash chain. |
| Metrics counters | `app/proxy/metrics.py` | In-memory counters: `pii_intercepted`, `tokens_scrubbed`, `threats_blocked`, `relay_ok`. |
| Internal API (admin) | `app/proxy/metrics_internal.py` | Token-gated endpoints: `GET /internal/metrics`, `GET /internal/logs`, `GET /internal/config`, `PATCH /internal/config`, `GET /internal/alerts`, `GET /internal/debug/prompt/{id}`, `DELETE /internal/rate_limits`. |
| Injection scanner | `app/proxy/injection.py` | Heuristic scan of prompt messages for injection patterns. Returns a finding with severity; `routes_chat` blocks or warns per `INJECTION_POLICY` env var. |
| Rate limiter | `app/proxy/rate_limit.py` | Per-key token budget and RPM limit. Uses tiktoken to estimate prompt token size. |
| Upstream client | `app/proxy/upstream_client.py` | `chat_completions_endpoint()`: correctly builds URL from base (avoids duplicate `/v1/v1` for Groq etc.). `post_chat_completion()`: sends the scrubbed request. |
| OpenAI schema | `app/proxy/openai_schema.py` | Pydantic models for `ChatCompletionRequest`, `ChatMessage`, etc. |
| Settings | `app/core/settings.py` | All config via env/`.env`: `UPSTREAM_BASE_URL`, `UPSTREAM_API_KEY`, `SHIELD_INTERNAL_TOKEN`, `VAULT_TTL_SECONDS`, `INJECTION_POLICY`, `SHADOW_MODE`, `DEMO_CHAT_ENABLED`, etc. |
| Config store | `app/proxy/config_store.py` | JSON file on disk that stores recognizer toggles and shadow mode. PATCH endpoint rebuilds Presidio engine live — no restart needed. |
| Shadow mode | setting + `routes_chat.py` | When enabled: Presidio still detects and logs PII, but does NOT replace spans before upstream. Used for evaluation/tuning without affecting real responses. |
| Signals (alerts, debug) | `app/proxy/signals.py` | `AlertRing`: ring buffer of critical alert events. `PromptDebugBuffer`: stores before/after scrub snapshots per correlation ID for the debug endpoint. |
| Dashboard | `app/dashboard/src/` | React + Vite + Tailwind + shadcn/ui. Three pages: Overview (metrics, flow diagram), Logs (audit rows, copy correlation ID), Config (toggle recognizers, shadow mode). Polls `/internal/*` every 5s. |
| Demo chat UI | `app/proxy/static/chat.html` | Single-file HTML+JS chat page at `/chat`. Sends to the gateway's own `/v1/chat/completions`. Used for demos and grading without needing a separate client app. |
| Tests | `tests/test_api_smoke.py`, `tests/test_upstream_url.py` | Smoke tests: health, OpenAPI docs available, internal routes need token, demo chat served, upstream URL construction (no duplicate `/v1`). |
| Docker | `Dockerfile`, `docker-compose.yml` | Single container: Python 3.12-slim, installs deps + spaCy model, exposes 8888. Docker Compose adds a named volume for `data/`. Healthcheck calls `/health`. |
| Setup wizard | `Setup-ShieldAI.ps1` | Interactive PowerShell script: asks for API URL/key, writes `.env`, optionally creates venv, installs Python deps + spaCy + npm, starts server. |

---

## Technologies used

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.11+ |
| Web framework | FastAPI | ≥ 0.115 |
| ASGI server | Uvicorn | ≥ 0.32 |
| PII detection | Microsoft Presidio Analyzer + Anonymizer | ≥ 2.2.354 |
| NLP model | spaCy `en_core_web_lg` | 3.x |
| Async HTTP | httpx | ≥ 0.27 |
| Config/validation | pydantic-settings | ≥ 2.6 |
| Token estimation | tiktoken | ≥ 0.8 |
| Database | SQLite (Python built-in) | — |
| Cache/vault option | Redis (hiredis) | ≥ 5.0 |
| Frontend framework | React 18 | Node 20+ |
| Frontend build | Vite | — |
| UI styling | Tailwind CSS + shadcn/ui | — |
| Containerization | Docker + Docker Compose | — |
| Tests | pytest + pytest-asyncio | — |

---

## Anonymization strategies (configurable via `ANON_STRATEGY` env var)

| Strategy | What happens | Example |
|----------|-------------|---------|
| `placeholder` (default) | Span replaced with typed token, stored in vault | `Ram Bahadur` → `<PERSON_1>` |
| `mask` | Span replaced with `*` characters | `Ram Bahadur` → `***********` |
| `hash` | Span replaced with a short SHA-256 hash | `Ram Bahadur` → `a3f9c2...` |

Only `placeholder` allows de-anonymization of the response. Mask and hash are one-way.

---

## Nepal-specific PII recognizers (custom-built for this project)

| Entity type | Pattern | Example match |
|-------------|---------|---------------|
| `NP_CITIZENSHIP_NUMBER` | `\b\d{2}-\d{2}-\d{2}-\d{5}\b` | `12-34-56-78901` |
| `NP_MOBILE_NUMBER` | `+977-97x/98x` or local `97x/98x` 10-digit | `+977-9812345678`, `9812345678` |
| `AWS_ACCESS_KEY_ID` | `AKIA[0-9A-Z]{16}` | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | 40-char alphanumeric (context-gated) | internal AWS secret |
| `STRIPE_API_KEY` | `sk_live_...`, `rk_live_...`, `pk_live_...` | `sk_live_abc123...` |

Plus Presidio built-ins: `PERSON`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `CREDIT_CARD`, `IBAN_CODE`, `IP_ADDRESS`, `URL`, `LOCATION`, and more.

---

## Audit log schema (what is stored, what is NOT)

Stored per event:
- Timestamp (UTC)
- Correlation ID (UUID per request)
- Risk level (low / medium / high / critical)
- Semantic risk level
- Entity type counts as JSON (e.g. `{"PERSON": 2, "NP_MOBILE_NUMBER": 1}`)
- Threat findings JSON (injection scan result)
- Total scrub entity count
- Whether shadow mode was used
- SHA-256 hash of the previous row (`prev_hash`)
- SHA-256 hash of this row (`row_hash`)

**NOT stored:** raw prompt text, original PII values, vault tokens. The chain proves rows have not been deleted or reordered without revealing what was in the prompts.

---

## Zero-trust framing (scope: AI egress only)

This project applies zero-trust narrowly to the AI data egress channel, not to the full enterprise network. The four principles applied:

1. **Never trust the external model** — always minimize the payload before it leaves the bank boundary (scrub first, always)
2. **Never trust the transport** — correlation IDs and hash chain allow forensic traceability even if external logs are tampered with
3. **Least privilege per request** — each request has its own vault key; vault entries expire after `VAULT_TTL_SECONDS`
4. **Continuous verification** — injection heuristics, rate/token budgets, shadow mode for tuning, operator dashboard for ongoing visibility

---

## What the project does NOT cover (honest limitations)

- Legal compliance certification — the code demonstrates technical controls; it is not a formal regulatory approval
- Production deployment at a real bank — this is a research prototype
- Full enterprise IAM, HSM, or multi-tenant key management
- Real customer or employee data (all evaluation is synthetic)
- Cross-border data transfer analysis or formal DPIA
- High availability, load balancing, or disaster recovery
- Streaming de-anonymization (streaming responses are buffered first, then de-anonymized as a whole)

---

## Regulatory context (Nepal)

**Nepal Rastra Bank (NRB) Cyber Resilience Guidelines**
- Regulator for Class 'A' commercial banks in Nepal
- Guidelines place obligations on licensed financial institutions for technical and organizational controls over data security, monitoring, incident response, and audit
- Exact section citations should be confirmed with your supervisor from the official NRB document

**Individual Privacy Act, 2018 (Vyaktigat Gupta Sauchana Sambandhi Ain, 2075)**
- Establishes legal obligations around collection, processing, storage, and sharing of personal information of Nepali citizens
- Key principles relevant to this project: data minimization, purpose limitation, security of processing, data retention, accountability
- Exact article citations should be confirmed with your supervisor

---

## Suggested report chapter structure

1. **Introduction** — background, motivation, problem statement, objectives, research questions, scope
2. **Literature Review** — LLM privacy risks, DLP systems, API proxy architectures, zero-trust models, prior work on privacy-preserving AI, Nepal banking regulatory context
3. **System Design and Architecture** — gateway placement, component design, data flow, anonymization pipeline, audit design, zero-trust framing
4. **Implementation** — technology stack, key modules (gateway, PII detection, Nepal recognizers, vault, audit, dashboard), development process
5. **Evaluation** — test methodology, synthetic scenarios, results (PII detection accuracy, latency, audit integrity), discussion
6. **Regulatory Alignment** — mapping implemented controls to NRB guidelines and Privacy Act themes, gap analysis
7. **Conclusion and Future Work** — summary of contributions, limitations, future work (streaming de-anonymization, `/ready` endpoint, full IAM, production hardening)
8. **References**

---

## Important instructions for the AI writing the report

- Use the thesis title exactly as written above — do not paraphrase or shorten it
- All technical claims must match what is described in this file — do not invent features
- The prototype is called **ShieldAI**
- Evaluation used **synthetic fictional data only** — state this clearly wherever evaluation is discussed
- When citing NRB guidelines or the Privacy Act, use phrasing like "as outlined in the NRB Cyber Resilience Guidelines" without inventing specific article numbers — leave those as [cite] placeholders for the student to fill in
- The project is a **prototype** / **proof-of-concept** — do not describe it as production software or as achieving regulatory compliance
- Write in formal academic English appropriate for a computer science / information security thesis
- The student is based in Kathmandu, Nepal; their institution and supervisor details are not included here and should be left as [Institution Name], [Supervisor Name] placeholders
