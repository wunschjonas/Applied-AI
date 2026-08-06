from __future__ import annotations

from pathlib import Path

from helpers import build_graph


def test_trace_steps_include_thought_action_observation(tmp_path: Path):
    graph = build_graph(tmp_path)
    result = graph.run("Schreibe einen LinkedIn Post ueber KI-Agenten.", "post-tao")
    trace = graph.trace_service.get_trace(result["trace_id"])

    assert trace["steps"], "expected at least one TAO step"
    assert len(trace["steps"]) >= 3
    assert all(
        step.get("thought") and step.get("action") and step.get("observation")
        for step in trace["steps"]
    )


def test_different_requests_produce_different_trace_text(tmp_path: Path):
    graph_a = build_graph(tmp_path / "a")
    graph_b = build_graph(tmp_path / "b")

    result_a = graph_a.run("Schreibe einen LinkedIn Post ueber KI-Agenten.", "post-gen")
    result_b = graph_b.run("Was weisst du ueber Aliens im Gedaechtnis?", "post-mem")

    steps_a = graph_a.trace_service.get_trace(result_a["trace_id"])["steps"]
    steps_b = graph_b.trace_service.get_trace(result_b["trace_id"])["steps"]

    text_a = " | ".join(f"{s['thought']}::{s['action']}::{s['observation']}" for s in steps_a)
    text_b = " | ".join(f"{s['thought']}::{s['action']}::{s['observation']}" for s in steps_b)

    assert text_a != text_b
    # Memory inquiry should mention memory/search somewhere in the composed German text.
    assert any(
        "memory" in (s.get("action") or "").lower()
        or "Memory" in (s.get("thought") or "")
        or "Gedächtnis" in (s.get("thought") or "")
        or "Wissensbasis" in (s.get("thought") or "")
        for s in steps_b
    )
