from __future__ import annotations

from pathlib import Path

from prometheus_client import REGISTRY

from helpers import FakeHF, FakeRAG, build_graph, seed_post

TEXT_PROMPT_MARKER = "Create marketing text for this task:"


def _seed_text_post(graph, post_id: str) -> None:
    seed_post(
        graph,
        post_id,
        topic="KI Agenten",
        platform="LinkedIn",
        target_audience="CMOs",
        tone_of_voice="professionell",
        text_context="KI-Agenten fuer Marketing-Workflows.",
        text_length="mittel",
    )


def _text_agent_calls(hf: FakeHF) -> int:
    return sum(1 for prompt in hf.user_prompts if TEXT_PROMPT_MARKER in prompt)


def _retry_text_count() -> float:
    value = REGISTRY.get_sample_value("manager_validation_total", {"result": "retry_text"})
    return value or 0.0


def test_short_text_triggers_one_retry_and_recovers(tmp_path: Path):
    hf = FakeHF(short_text_failures=1)
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=FakeRAG(""))
    _seed_text_post(graph, "post-retry-text")

    before = _retry_text_count()
    from helpers import run_generation

    result = run_generation(graph, "post-retry-text", intent="text_only")
    metadata = graph.trace_service.get_trace(result["trace_id"])["metadata"]

    assert _retry_text_count() == before + 1
    assert metadata["retry_count"]["text"] == 1
    assert metadata["status"] == "success"
    assert _text_agent_calls(hf) == 2
    assert len(result["generated_artifacts"]["text"]["generated_text"]) >= 180
