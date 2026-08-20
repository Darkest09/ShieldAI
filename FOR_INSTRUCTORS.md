# For instructors / grading (minimal steps)

ShieldAI is a **local API** plus an optional **browser chat page** so you can try prompts **without PowerShell**.

## Option A — Docker (recommended if Docker Desktop is installed)

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows / Mac).
2. Unzip the project. Copy **`.env.example`** → **`.env`** and set at least **`UPSTREAM_BASE_URL`** and **`UPSTREAM_API_KEY`**. Docker Compose reads **`.env` from disk** — create this file before the next step or `docker compose` may error.
3. In the project folder, run:

   ```bash
   docker compose up --build
   ```

4. Open a browser:
   - **Chat UI:** **http://localhost:8888/chat** (or **http://127.0.0.1:8888/chat**)
   - **API docs:** **http://localhost:8888/docs**

5. Stop: `Ctrl+C` in the terminal, or `docker compose down`.

First boot may take a few minutes while the image downloads dependencies and the spaCy model.

---

## Option B — Windows script (no Docker)

After unzip from **`ShieldAI_share_*.zip`**, run **`Setup-ShieldAI.ps1`** at the folder root (same level as `pyproject.toml`) — it asks for **`UPSTREAM_*`** and can install Python/npm then start the API. See **`SHARE_FIRST.txt`**.

Or manually:

1. Install **Python 3.11+** (check “Add to PATH”).
2. Copy **`.env.example`** → **`.env`** and fill **`UPSTREAM_*`** (and any other keys the student README lists).
3. Double‑click or run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\start-teacher.ps1
   ```

4. When the server is ready, the script opens **http://127.0.0.1:8888/chat** in your browser.

---

## What to try in the chat page

- Normal question (should answer).
- Text containing **fake** email / “AWS key” style strings (should still respond; the proxy scrubs before upstream — see **Security logs** in the full dashboard if the student runs it).

---

## Turn off the demo page (production)

In **`.env`**: **`DEMO_CHAT_ENABLED=false`** — then **`/chat`** is not served (API and **`/docs`** still work).

---

## Connecting a different web chat (React, etc.)

See **`INTEGRATION.md`** in the project: set **`EXTRA_CORS_ORIGINS`** to your app’s URL (e.g. `http://localhost:3000`) and call **`POST http://<shieldai-host>:8888/v1/chat/completions`** from the browser or use any OpenAI-compatible SDK with **`base_url`** pointing at ShieldAI’s **`/v1`**.
