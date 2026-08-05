from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from helpers import FakeHF, FakeRAG, build_graph, seed_post


def test_metrics_endpoint_exposes_prometheus_text():
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "# HELP" in body
    assert "http_" in body
    assert "manager_chat_requests_total" in body


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


def test_manager_graph_increments_custom_metrics(tmp_path: Path):
    hf = FakeHF()
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=FakeRAG(""))
    seed_post(graph, "post-metrics", topic="Fußball")
    graph.run("Schreibe bitte einen LinkedIn Post.", "post-metrics")

    client = TestClient(app)
    body = client.get("/metrics").text
    assert "manager_chat_requests_total" in body
    assert "manager_chat_intent_total" in body
    assert "manager_chat_route_total" in body
    assert any(
        line.startswith("manager_chat_requests_total{") and " " in line
        for line in body.splitlines()
        if not line.startswith("#")
    )
