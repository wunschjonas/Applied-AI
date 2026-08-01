from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.rag_service import chunk_text
from tests.test_phase1_agent_refactor import FakeHF, FakeRAG, build_graph, seed_post


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

    result = graph.run("Was steht in deinem Rag / Gedaechtnis?", "post-memory-q")

    assert rag.retrieve_called or rag.list_all()
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
