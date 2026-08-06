from __future__ import annotations

from pathlib import Path

from prometheus_client import REGISTRY

from helpers import FakeHF, FakeRAG, build_graph, seed_post

TEXT_PROMPT_MARKER = "Create marketing text for this task:"


class CountingHF(FakeHF):
    """FakeHF that tracks how often a text-to-image generation was requested."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.image_calls = 0

    def generate_image(self, prompt: str, negative_prompt: str | None = None) -> bytes:
        self.image_calls += 1
        return super().generate_image(prompt, negative_prompt)


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
    result = graph.run("Schreibe bitte einen LinkedIn Post.", "post-retry-text")
    metadata = graph.trace_service.get_trace(result["trace_id"])["metadata"]

    assert _retry_text_count() == before + 1
    assert metadata["retry_count"]["text"] == 1
    assert metadata["status"] == "success"
    assert _text_agent_calls(hf) == 2
    assert len(result["generated_artifacts"]["text"]["generated_text"]) >= 180


def test_second_text_failure_does_not_retry_again(tmp_path: Path):
    hf = FakeHF(short_text_failures=2)
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=FakeRAG(""))
    _seed_text_post(graph, "post-retry-exhausted")

    result = graph.run("Schreibe bitte einen LinkedIn Post.", "post-retry-exhausted")
    trace = graph.trace_service.get_trace(result["trace_id"])
    metadata = trace["metadata"]
    validation_states = [
        step.get("status") for step in trace["steps"] if step.get("agent") == "validation_node"
    ]

    assert metadata["retry_count"]["text"] == 1
    assert _text_agent_calls(hf) == 2
    # Second failure ends validation instead of retrying again.
    assert validation_states[-1] == "failed"
    # The run still returns a partial answer rather than dropping the artifact.
    assert metadata["status"] == "partial_success"
    assert result["assistant_message"]


def test_text_retry_keeps_existing_image(tmp_path: Path):
    post_id = "11111111-2222-3333-4444-666666666666"
    hf = CountingHF(short_text_failures=1)
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=FakeRAG(""))
    seed_post(
        graph,
        post_id,
        topic="KI Agenten",
        platform="Instagram",
        target_audience="Marketing-Teams",
        tone_of_voice="locker",
        text_context="KI-Agenten helfen Marketing-Teams bei Content und Automation.",
        text_length="mittel",
        image_context="Modernes Team vor einem KI-Dashboard",
        image_style="clean commercial",
    )

    result = graph.run("Erstelle eine Instagram Caption mit Hashtags und Bildidee.", post_id)
    metadata = graph.trace_service.get_trace(result["trace_id"])["metadata"]

    assert metadata["retry_count"]["text"] == 1
    assert _text_agent_calls(hf) == 2
    # The image was valid before the text retry, so it must not be generated again.
    assert hf.image_calls == 1
    assert result["generated_artifacts"]["image"]["image_filename"] == f"{post_id}.png"
