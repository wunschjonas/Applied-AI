from __future__ import annotations

from pathlib import Path

from helpers import FakeHF, FakeRAG, build_graph, seed_post


def test_incomplete_brief_uses_completeness_tool(tmp_path: Path):
    hf = FakeHF()
    rag = FakeRAG("")
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=rag)
    seed_post(graph, "post-incomplete", topic="Nur Thema")

    result = graph.run("Schreibe bitte einen LinkedIn Post.", "post-incomplete")
    trace = graph.trace_service.get_trace(result["trace_id"])
    actions = [step.get("action") or "" for step in trace["steps"]]

    assert any("check_post_data_completeness" in a for a in actions)
    assert "TextAgent" not in (result.get("used_agents") or [])
    assert result.get("assistant_message")


def test_memory_store_on_explicit_user_request(tmp_path: Path):
    hf = FakeHF()
    rag = FakeRAG("")
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=rag)
    seed_post(
        graph,
        "post-store",
        topic="Brand",
        platform="LinkedIn",
        target_audience="CMOs",
        tone_of_voice="klar",
    )
    result = graph.run(
        "Merk dir bitte: Unsere Markenfarbe ist Petrolblau.",
        "post-store",
    )
    trace = graph.trace_service.get_trace(result["trace_id"])
    actions = [step.get("action") or "" for step in trace["steps"]]
    assert any("memory_store" in a for a in actions)
    assert rag.stored
    assert any("Petrolblau" in content for content, _ in rag.stored)
