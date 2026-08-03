from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.graphs.support.post_fields import is_memory_inquiry, memory_search_query
from app.main import app
from app.services.rag_service import chunk_text
from tests.test_phase1_agent_refactor import FakeHF, FakeRAG, build_graph, seed_post


def test_memory_topic_query_extraction():
    assert is_memory_inquiry("Was steht zum Thema Formel 1 im Rag?")
    assert memory_search_query("Was steht zum Thema Formel 1 im Rag?") == "formel 1"
    assert "zielgruppe" in memory_search_query("Was weisst du im Gedaechtnis ueber die Zielgruppe?")
    assert is_memory_inquiry("Was weisst du ueber Formel 1?")
    assert memory_search_query("Was weisst du ueber Formel 1?") == "formel 1"
    assert is_memory_inquiry("Kennst du Details zur Kampagne Q3?")
    assert "kampagne" in memory_search_query("Kennst du Details zur Kampagne Q3?")
    assert not is_memory_inquiry("Was wissen wir schon zum aktuellen Post?")


def test_chunk_text_splits_long_content():
    text = "word " * 400
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    assert all(chunks)
    assert chunk_text("   ") == []
    assert chunk_text("short note") == ["short note"]


def test_react_rag_calls_memory_search_tool(tmp_path: Path):
    hf = FakeHF()
    rag = FakeRAG("brand guideline memory")
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=rag)
    seed_post(
        graph,
        "post-react-rag",
        topic="KI Agenten",
        platform="LinkedIn",
        target_audience="CMOs",
        tone_of_voice="professionell",
    )

    result = graph.run(
        "Schreibe einen LinkedIn Post basierend auf unserem PDF mit Brand Guidelines.",
        "post-react-rag",
    )

    assert rag.retrieve_called
    assert rag.search_queries
    assert any(round_["tools"] for round_ in hf.tool_rounds)
    trace = graph.trace_service.get_trace(result["trace_id"])
    assert any(step["action"] == "call_memory_search" for step in trace["steps"])
    assert result["used_agents"] == ["TextAgent"]


def test_memory_inquiry_answers_from_rag(tmp_path: Path):
    hf = FakeHF()
    rag = FakeRAG("Uploaded image hero.png: a blue electric car on a road")
    rag.stored.append((rag.result, ["upload", "image"]))
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=rag)
    seed_post(graph, "post-memory-q")

    result = graph.run("Was steht zum Thema Elektroauto im Rag?", "post-memory-q")

    assert rag.retrieve_called or rag.list_all()
    assert rag.search_queries
    assert "elektroauto" in rag.search_queries[0].lower()
    assert "car" in result["assistant_message"].lower() or "ged" in result["assistant_message"].lower() or "memory" in result["assistant_message"].lower() or "bild" in result["assistant_message"].lower() or "eintrag" in result["assistant_message"].lower() or "gefunden" in result["assistant_message"].lower()
    assert result["used_agents"] == []
    # Must not poison platform with the chat question.
    post = graph.post_repository.get("post-memory-q")
    assert post.get("platform") in (None, "linkedin", "instagram", "x", "blog", "tiktok", "facebook")


def test_react_rag_skips_when_model_declines_tool(tmp_path: Path):
    hf = FakeHF()
    rag = FakeRAG("should not be used")
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=rag)
    seed_post(
        graph,
        "post-no-rag",
        topic="KI Agenten",
        platform="LinkedIn",
        target_audience="CMOs",
        tone_of_voice="professionell",
    )

    result = graph.run("Schreibe einen LinkedIn Post ueber KI-Agenten im Marketing.", "post-no-rag")

    assert not rag.retrieve_called
    assert result["used_agents"] == ["TextAgent"]
    trace = graph.trace_service.get_trace(result["trace_id"])
    assert any(step["action"] == "skip_memory_search" for step in trace["steps"])


def test_upload_pdf_chunks_into_memory(tmp_path: Path):
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    # pypdf blank pages have no text; inject via mock extract instead.
    pdf_bytes = BytesIO()
    writer.write(pdf_bytes)
    pdf_bytes.seek(0)

    rag = FakeRAG()
    hf = FakeHF()

    with (
        patch("app.api.routes_memory.rag_service", rag),
        patch("app.api.routes_memory._extract_pdf_text", return_value=("Brand voice is clear and confident. " * 80)),
        patch("app.api.routes_memory.settings") as settings_mock,
    ):
        settings_mock.uploads_dir = tmp_path / "uploads"
        settings_mock.mcp_memory_url = "http://localhost:8765/mcp"
        settings_mock.hf_token = None
        client = TestClient(app)
        response = client.post(
            "/api/memory/upload",
            files={"file": ("brand.pdf", pdf_bytes.getvalue(), "application/pdf")},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "pdf"
    assert body["stored_chunks"] >= 1
    assert len(rag.stored) == body["stored_chunks"]
    assert "upload" in rag.stored[0][1]


def test_upload_image_stores_caption(tmp_path: Path):
    rag = FakeRAG()
    hf = FakeHF()

    with (
        patch("app.api.routes_memory.rag_service", rag),
        patch("app.api.routes_memory.HuggingFaceService", return_value=hf),
        patch("app.api.routes_memory.settings") as settings_mock,
    ):
        settings_mock.uploads_dir = tmp_path / "uploads"
        settings_mock.hf_token = type("T", (), {"get_secret_value": lambda self: "token"})()
        settings_mock.hf_model_id = "fake"
        settings_mock.hf_image_model_id = "fake-image"
        client = TestClient(app)
        response = client.post(
            "/api/memory/upload",
            files={"file": ("hero.png", b"fake-png-bytes", "image/png")},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "image"
    assert body["stored_chunks"] == 1
    assert "marketing product photo" in rag.stored[0][0]
    assert (tmp_path / "uploads").exists()


def test_memory_list_and_delete_by_hash(tmp_path: Path):
    rag = FakeRAG()
    rag.store("Brand voice is clear.", ["brand"])
    rag.store("Target audience is CMOs.", ["audience"])

    with patch("app.api.routes_memory.rag_service", rag):
        client = TestClient(app)
        listed = client.get("/api/memory/list")
        assert listed.status_code == 200
        entries = listed.json()["entries"]
        assert len(entries) == 2
        assert entries[0]["content_hash"] == "hash-0"

        deleted = client.delete(f"/api/memory/{entries[0]['content_hash']}")
        assert deleted.status_code == 200
        assert deleted.json()["status"] == "deleted"

        remaining = client.get("/api/memory/list").json()["entries"]
        assert len(remaining) == 1
        assert remaining[0]["content"] == "Target audience is CMOs."

        missing = client.delete("/api/memory/hash-999")
        assert missing.status_code == 404
