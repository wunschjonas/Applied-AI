from __future__ import annotations

from pathlib import Path

from helpers import FakeHF, FakeRAG, build_graph, seed_post


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
    assert any("memory_search" in (step.get("action") or "") for step in trace["steps"])
    assert result["used_agents"] == ["TextAgent"]
