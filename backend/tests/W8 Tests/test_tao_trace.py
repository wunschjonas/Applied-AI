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
