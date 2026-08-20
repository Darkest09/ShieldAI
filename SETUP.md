# ShieldAI — fresh setup & GitHub

## What belongs on GitHub (and in the offline backup folder)

Included in Git / backup:

- Source code: `app/`, `tests/`, `scripts/`, `pyproject.toml`, `.gitignore`, `.env.example`, `README.md`, `SETUP.md`, `FOR_INSTRUCTORS.md`, `INTEGRATION.md`, `Dockerfile`, `docker-compose.yml`, `Setup-ShieldAI.ps1`, `SHARE_FIRST.txt`

Excluded (do **not** commit):

- **`data/`** — local SQLite audit DB, persisted config JSON (may contain sensitivity); recreated at runtime  
- **`app/dashboard/node_modules/`** — reinstall with `npm install`  
- **`node_modules`** anywhere — same  
- **`app/dashboard/dist/`** — build output from `npm run build`  
- **`.env`** — secrets (`UPSTREAM_API_KEY` / legacy `OPENAI_API_KEY`, tokens); commit **`.env.example`** only  
- **`__pycache__/`, `.pytest_cache/`, `*.egg-info/`** — toolchain noise  
- **`.venv` / `venv`** — recreate locally  

Mirrors are produced by **`scripts/export-github-backup.ps1`** (drops a folder next to your repo named **`ShieldAI_github_backup`**, omitting those paths).

To hand a **fresh zip** to someone else: **`scripts/make-share-bundle.ps1`** (folder + `.zip` by default). Recipients read **`SHARE_FIRST.txt`** and run **`Setup-ShieldAI.ps1`** at the repo root for guided **`.env`** + optional **venv / pip / spaCy / npm / start**. Folder-only: **`make-share-bundle.ps1 -NoZip`**.

## Fresh machine setup (development)

### 1. Prerequisites

- **Python ≥ 3.11** (`python --version`)  
- **Node.js ≥ 20** with npm (`node --version`, `npm --version`)  
- **Git**

### 2. Clone / copy project

Either clone from GitHub after you push, or unzip/copy a **`ShieldAI_share_*.zip`** from **`scripts/make-share-bundle.ps1`** and `cd` into it — then run **`Setup-ShieldAI.ps1`** or see **`SHARE_FIRST.txt`**.

### 3. Backend (ShieldAI FastAPI proxy)

From the **repository root** (where `pyproject.toml` lives):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -e ".[dev]"
```

Create runtime directories and secrets file:

```powershell
New-Item -ItemType Directory -Force data | Out-Null
Copy-Item .env.example .env
# Edit .env: UPSTREAM_BASE_URL + UPSTREAM_API_KEY (or OPENAI_* / LLM_API_KEY aliases), SHIELD_INTERNAL_TOKEN, etc.
```

Configure **`UPSTREAM_BASE_URL`** and **`UPSTREAM_API_KEY`** for any OpenAI-compatible provider (OpenAI, Groq, OpenRouter, local Ollama, …). Legacy **`OPENAI_*`** and **`LLM_API_KEY`** still map to the same settings—see `.env.example`.

Install spaCy model (required by Presidio at runtime):

```powershell
python -m spacy download en_core_web_lg
```

(Optional) Place **`en_core_web_lg`** wheel or unpacked model under **`./data/`** so startup can consume it offline — see `app/core/spa_cache.py`.

Run API (`vite.config.ts` proxies to **`http://127.0.0.1:8888`** by default — avoids Windows **`WinError 10013`** on ports like `8010`):

```powershell
python -m uvicorn app.proxy.main:app --reload --host 127.0.0.1 --port 8888
```

Smoke check: http://127.0.0.1:8888/docs  

**Browser chat (no PowerShell):** **http://127.0.0.1:8888/chat** — minimal UI that calls the same **`POST /v1/chat/completions`** as apps. Turn off with **`DEMO_CHAT_ENABLED=false`** in `.env` on shared servers.

**Easiest Windows handoff for grading:** `powershell -ExecutionPolicy Bypass -File .\scripts\start-teacher.ps1` (creates `.venv`, installs deps, checks spaCy, opens `/chat`).

**Docker handoff:** see **[FOR_INSTRUCTORS.md](FOR_INSTRUCTORS.md)** (`docker compose up --build`).

**Third-party chat apps / OpenAI SDKs:** see **[INTEGRATION.md](INTEGRATION.md)** (`EXTRA_CORS_ORIGINS`, `base_url`).

If you must use another port, set the same URL in **`app/dashboard/.env.development`** as **`VITE_SHIELD_API_URL=http://127.0.0.1:<PORT>`**.

### 4. Frontend (dashboard)

```powershell
cd app\dashboard
npm install
```

Ensure **`app/dashboard/.env.development`** (or `.env.local`) aligns with the backend:

```env
VITE_INTERNAL_TOKEN=<same-as-SHIELD_INTERNAL_TOKEN-in-backend-.env>
VITE_SHIELD_API_URL=http://127.0.0.1:8888
```

Run Vite (proxies `/internal` and `/v1` — target from **`VITE_SHIELD_API_URL`** or default **`8888`**):

```powershell
npm run dev -- --host 127.0.0.1 --port 5173
```

Open http://127.0.0.1:5173

### 5. One-shot dev launcher (Windows)

From repo root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```

Opens two windows: uvicorn + Vite.

### 6. Tests

```powershell
# from repo root, venv active
python -m pytest tests -q
```

### 7. Publish to GitHub

```powershell
cd C:\path\to\your-clean-copy
git init
git add .
git commit -m "Initial commit: ShieldAI proxy hardening baseline"
git branch -M main
git remote add origin https://github.com/<YOU>/<YOUR-REPO>.git
git push -u origin main
```

Prefer **`git`** over drag-and-drop: it respects `.gitignore` automatically.

If using the **`ShieldAI_github_backup`** folder produced by `export-github-backup.ps1`:

1. Inspect that folder.  
2. `git init` there **or** paste its contents into a fresh clone minus secrets.  
3. Never paste real `.env` or production `data/*.db`.

## Production notes (beyond local dev)

- Run behind TLS termination (reverse proxy).  
- Set strong **`SHIELD_INTERNAL_TOKEN`** and **rotate** routinely.  
- Restrict **`DASHBOARD_ORIGINS`** / CORS to real admin UI origins only.  
- Back up **`data/`** with normal DB backup practice if audits matter (outside Git).
