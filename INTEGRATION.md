# Integrating other apps & chat UIs with ShieldAI

ShieldAI speaks the **OpenAI HTTP API**: **`POST /v1/chat/completions`** with JSON body `{ "model", "messages", ... }`. Any tool that can point at a custom **base URL** can sit in front of ShieldAI instead of calling OpenAI (or Groq) directly.

## 1. Built-in demo chat

Open **`http://127.0.0.1:8888/chat`** (same host as the API). No extra setup.

## 2. Another web app on a **different port** (browser `fetch`)

Browsers block cross-origin calls unless ShieldAI allows your origin.

In **`.env`**, add your app’s origin to **`EXTRA_CORS_ORIGINS`** (comma-separated), **in addition to** anything you already set in **`DASHBOARD_ORIGINS`**:

```env
DASHBOARD_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
EXTRA_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:4173
```

Restart **uvicorn**. Your chat UI can then:

```javascript
const res = await fetch('http://127.0.0.1:8888/v1/chat/completions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: 'openai/gpt-oss-120b',
    messages: [{ role: 'user', content: 'Hello' }],
  }),
});
```

Use the **exact host + port** your UI is served from (including `http` vs `https`).

## 3. OpenAI official SDKs (Python / Node)

Point **`base_url`** at ShieldAI’s **`/v1`** prefix (same rule as env: host + `/v1`).

**Python**

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8888/v1",
    api_key="not-used-locally",  # ShieldAI uses UPSTREAM_API_KEY from .env for the real provider
)
r = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[{"role": "user", "content": "Hi"}],
)
print(r.choices[0].message.content)
```

**Node**

```javascript
import OpenAI from 'openai';

const openai = new OpenAI({
  baseURL: 'http://127.0.0.1:8888/v1',
  apiKey: 'not-used-locally',
});
```

If the SDK insists on an API key, any non-empty placeholder is fine; ShieldAI still authenticates **upstream** with **`UPSTREAM_API_KEY`**.

## 4. LangChain, LlamaIndex, etc.

Use their **OpenAI-compatible chat model** integration and set:

- **Base URL:** `http://127.0.0.1:8888/v1` (or your deployed host)
- **API key:** dummy or real per their docs
- **Model:** whatever your upstream (e.g. Groq) accepts

## 5. Optional: rate / budget key

ShieldAI can read **`X-ShieldAI-Key`** on requests for token-budget accounting. Optional for simple demos.

## 6. Production checklist

- Set **`DEMO_CHAT_ENABLED=false`** if you do not want the HTML page on a public host.
- Tighten **`DASHBOARD_ORIGINS`** and **`EXTRA_CORS_ORIGINS`** to known frontends only.
- Put ShieldAI **behind HTTPS** and use **`https://…/v1`** in client configs.
