from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_manager_chat_rejects_empty_message():
    response = client.post(
        "/api/agents/manager/chat",
        json={"message": "", "post_id": "post-1"},
    )
    assert response.status_code == 422


def test_manager_chat_unknown_post_returns_404():
    response = client.post(
        "/api/agents/manager/chat",
        json={"message": "Schreibe einen Post", "post_id": "does-not-exist-xyz"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Post not found"
