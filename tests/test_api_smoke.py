from fastapi.testclient import TestClient

from app.core.settings import settings
from app.proxy.main import app


def test_health_openapi_documentation_available() -> None:
    client = TestClient(app)
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert r.json()["info"]["title"] == "ShieldAI"


def test_health_liveness() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "shieldai"}


def test_internal_metrics_requires_token() -> None:
    client = TestClient(app)
    assert client.get("/internal/metrics").status_code == 401


def test_internal_metrics_with_token() -> None:
    client = TestClient(app)
    r = client.get(
        "/internal/metrics",
        headers={"X-Shield-Internal-Token": settings.shield_internal_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert "pii_intercepted_total" in data


def test_internal_alerts_requires_token() -> None:
    client = TestClient(app)
    assert client.get("/internal/alerts").status_code == 401


def test_internal_prompt_debug_requires_token() -> None:
    client = TestClient(app)
    assert client.get("/internal/debug/prompt/demo").status_code == 401


def test_demo_chat_page_served() -> None:
    client = TestClient(app)
    r = client.get("/chat")
    assert r.status_code == 200
    assert "ShieldAI" in r.text
    assert settings.demo_chat_default_model in r.text


def test_root_redirects_to_demo_chat() -> None:
    client = TestClient(app)
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307, 308)
    loc = r.headers.get("location") or ""
    assert loc.endswith("/chat")
