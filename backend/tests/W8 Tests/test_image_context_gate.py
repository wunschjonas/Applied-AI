from __future__ import annotations

from pathlib import Path

from app.graphs.support.post_fields import (
    missing_fields_for_intent,
    next_question,
)
from helpers import FakeHF, FakeRAG, build_graph, seed_post


def test_missing_fields_for_intent_requires_text_and_image_extras():
    post = {
        "topic": "Nationalmannschaft",
        "platform": "linkedin",
        "target_audience": "Fans",
        "tone_of_voice": "stolz",
    }
    text_missing = missing_fields_for_intent(post, "text_only")
    assert "text_context" in text_missing
    assert "text_length" in text_missing
    assert "image_context" not in text_missing

    image_missing = missing_fields_for_intent(post, "image_only")
    assert "image_context" in image_missing
    assert "image_style" in image_missing
    assert "text_context" not in image_missing

    both = missing_fields_for_intent(post, "text_and_image")
    assert "text_context" in both
    assert "text_length" in both
    assert "image_context" in both
    assert "image_style" in both

    field, question = next_question(post, "text_and_image")
    assert field == "text_context"
    assert "Text" in question or "text" in question.lower() or "sagen" in question.lower()

    field_img, question_img = next_question(post, "image_only")
    assert field_img == "image_context"
    assert "Bild" in question_img or "bild" in question_img.lower()


def test_generate_with_only_topic_is_blocked(tmp_path: Path):
    """explicit_generate must not bypass incomplete Steckbrief."""
    hf = FakeHF()
    original = FakeHF.chat_with_tools

    def no_tools(self, messages, tools, max_tokens: int = 400, temperature: float = 0.2):
        self.tool_rounds.append({"messages": messages, "tools": tools})
        return {"content": "No tools.", "tool_calls": []}

    FakeHF.chat_with_tools = no_tools
    try:
        graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=FakeRAG(""))
        seed_post(graph, "post-topic-only", topic="Deutsche Nationalmannschaft")
        result = graph.run(
            "Erstelle Text und Bild zum Thema deutsche Nationalmannschaft.",
            "post-topic-only",
        )
        assert "TextAgent" not in (result.get("used_agents") or [])
        assert "ImageAgent" not in (result.get("used_agents") or [])
        message = (result.get("assistant_message") or "").lower()
        assert any(
            marker in message
            for marker in ("plattform", "zielgruppe", "tonal", "worum", "bildmotiv", "noch")
        )
        trace = graph.trace_service.get_trace(result["trace_id"])
        assert any(step.get("agent") == "context_question_node" for step in trace["steps"]) or any(
            "Steckbrief-Frage" in (step.get("action") or "") or "Safety" in (step.get("thought") or "")
            for step in trace["steps"]
        )
    finally:
        FakeHF.chat_with_tools = original


def test_bildmotiv_briefing_does_not_generate_image(tmp_path: Path):
    """Describing Bildmotiv must store image_context, not run ImageAgent."""
    from app.agents.manager_agent import ManagerIntentClassifier
    from app.graphs.support.post_fields import extract_fields, is_image_motif_briefing

    message = (
        "Im Bildmotiv soll der Gewinner der WM 2022 und der Gewinner der WM 2014 "
        "in einem Fußballspiel gegeneinander spielen. Im Hintergrund sieht man die Flaggen der Mannschaften"
    )
    assert is_image_motif_briefing(message)
    intent = ManagerIntentClassifier().classify_intent(message)
    assert intent.label == "clarification_needed"
    assert intent.use_image is False

    updates = extract_fields(message, {"topic": "Fußball"})
    assert "image_context" in updates
    assert "WM 2022" in updates["image_context"] or "Gewinner" in updates["image_context"]

    hf = FakeHF()
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=FakeRAG(""))
    seed_post(
        graph,
        "post-motif-only",
        topic="Fußball WM",
        platform="LinkedIn",
        target_audience="Fans",
        tone_of_voice="sportlich",
    )
    result = graph.run(message, "post-motif-only")
    assert "ImageAgent" not in (result.get("used_agents") or [])
    assert "TextAgent" not in (result.get("used_agents") or [])
    post = graph.post_repository.get("post-motif-only")
    assert post and post.get("image_context")
    assert "Flaggen" in post["image_context"] or "WM" in post["image_context"]
    trace = graph.trace_service.get_trace(result["trace_id"])
    assert any(step.get("agent") == "clarification_node" for step in trace["steps"])
    assert not any(step.get("agent") == "image_agent_node" for step in trace["steps"])
    message_out = (result.get("assistant_message") or "").lower()
    assert "bild" in message_out or "text" in message_out or "notiert" in message_out or "soll ich" in message_out
