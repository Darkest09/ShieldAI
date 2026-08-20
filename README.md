# ShieldAI — Privacy-Preserving AI Gateway (PPAG)

Zero-Trust privacy gateway between users and any OpenAI-compatible LLM (FastAPI + Presidio scrub + reversible vault + audited SQLite trail + React dashboard). Configure **`UPSTREAM_*`** env vars for any compatible LLM provider—see `.env.example`.

**PPAG capabilities** (see [PROPOSAL_TRACEABILITY.md](PROPOSAL_TRACEABILITY.md) for the full proposal→code map):
- **Zero-Trust access** — JWT login (`POST /v1/auth/token`) + RBAC roles + per-request context risk scoring. Enable with `ZERO_TRUST_ENABLED=true`.
- **Compliance enforcement** — policy engine (block/hold/warn/redact) mapped to NRB Cyber Resilience, Individual Privacy Act 2018, ISO 27001, NIST 800-207, OWASP-LLM. Coverage at `GET /internal/compliance/report` and the dashboard **Governance** tab.
- **Privacy** — reversible tokenisation + optional **AES-256-GCM** vault encryption (`VAULT_ENCRYPTION_KEY`).
- **PII detection** — primary backend is a **Hugging Face transformer** (`NLP_ENGINE=transformers`, 100% recall on the eval set); auto-falls back to fast spaCy if torch isn't installed. Install the heavy extra with `pip install -e ".[transformers]"`.
- **Governance** — high-risk prompts held for **human approval** (`/internal/approvals`); transparent, user-facing policy explanations.
- **Evaluation harness** — `scripts/generate_synthetic_dataset.py` + `scripts/evaluate.py` produce precision/recall/F1, FP/FN, and latency on a labelled synthetic Nepali-banking dataset.

- **One-click GUI (Windows):** double-click **`ShieldAI.cmd`** (or run `ShieldAI-Launcher.ps1`) for a control panel that installs deps, starts/stops the API + dashboard, opens the demo pages, verifies the audit chain, and runs tests — no terminal needed.
- **Quick start:** [SETUP.md](SETUP.md) (venv, `npm install`, API **8888** + Vite **5173**) · **Grading / Docker:** [FOR_INSTRUCTORS.md](FOR_INSTRUCTORS.md) · **Other chat UIs / SDKs:** [INTEGRATION.md](INTEGRATION.md)
- **Try prompts in the browser:** with the API running, open **http://127.0.0.1:8888/chat** (no PowerShell). Turn off with **`DEMO_CHAT_ENABLED=false`** in `.env` on public servers.
- **Offline GitHub-ish copy (Windows):** `powershell -ExecutionPolicy Bypass -File .\scripts\export-github-backup.ps1` writes `..\ShieldAI_github_backup` (excludes `node_modules`, `.env`, `data/`, `.git`, etc.).
- **Share with others:** `powershell -ExecutionPolicy Bypass -File .\scripts\make-share-bundle.ps1` builds a clean `..\ShieldAI_share_*` folder **and** `..\ShieldAI_share_*.zip` (no `node_modules`, `.venv`, `data/`, `.git`, `.env`). Recipients unzip, open **`SHARE_FIRST.txt`**, then run **`Setup-ShieldAI.ps1`** for prompts (API URL/key, optional auto-install + start). Use `-NoZip` on the bundle script for folder-only.
