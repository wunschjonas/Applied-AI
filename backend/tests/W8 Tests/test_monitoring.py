from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_includes_components():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert "status" in payload
    assert payload["status"] in {"ok", "degraded"}
    assert payload["service"] == "applied-ai-marketing-agent"
    assert "version" in payload
    components = payload["components"]
    assert "storage" in components
    assert components["storage"]["status"] in {"up", "down"}
    assert "memory" in components
    assert components["memory"]["status"] in {"up", "down"}
    assert "configured" in components["huggingface"]
    assert "enabled" in components["web_search"]
