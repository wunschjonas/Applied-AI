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
    # Skip completeness tool on purpose — router safety-net must still block.
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


def test_image_intent_blocks_without_image_context(tmp_path: Path):
    hf = FakeHF()
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=FakeRAG(""))
    seed_post(
        graph,
        "post-no-motif",
        topic="Deutsche Nationalmannschaft",
        platform="LinkedIn",
        target_audience="Fußballfans",
        tone_of_voice="stolz",
    )
    result = graph.run("Erstelle bitte nur ein Bild dazu.", "post-no-motif")
    assert "ImageAgent" not in (result.get("used_agents") or [])
    message = (result.get("assistant_message") or "").lower()
    assert "bild" in message or "motiv" in message


def test_image_intent_blocks_without_image_style(tmp_path: Path):
    hf = FakeHF()
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=FakeRAG(""))
    seed_post(
        graph,
        "post-no-style",
        topic="Deutsche Nationalmannschaft",
        platform="LinkedIn",
        target_audience="Fußballfans",
        tone_of_voice="stolz",
        image_context="Zwei Spieler und Flaggen",
    )
    result = graph.run("Erstelle bitte nur ein Bild dazu.", "post-no-style")
    assert "ImageAgent" not in (result.get("used_agents") or [])
    message = (result.get("assistant_message") or "").lower()
    assert "stil" in message or "style" in message or "bild" in message


def test_text_intent_blocks_without_text_context(tmp_path: Path):
    hf = FakeHF()
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=FakeRAG(""))
    seed_post(
        graph,
        "post-no-text-ctx",
        topic="Deutsche Nationalmannschaft",
        platform="LinkedIn",
        target_audience="Fußballfans",
        tone_of_voice="stolz",
    )
    result = graph.run("Schreibe bitte einen LinkedIn Post dazu.", "post-no-text-ctx")
    assert "TextAgent" not in (result.get("used_agents") or [])
    message = (result.get("assistant_message") or "").lower()
    assert any(token in message for token in ("text", "kontext", "laenge", "länge", "sagen", "lang"))


def test_image_agent_calls_get_post_data(tmp_path: Path):
    hf = FakeHF()
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=FakeRAG(""))
    seed_post(
        graph,
        "post-img-tool",
        topic="Deutsche Nationalmannschaft",
        platform="LinkedIn",
        target_audience="Fußballfans",
        tone_of_voice="stolz",
        image_context="Deutscher Spieler, Flaggen von Kanada Mexiko USA im Hintergrund",
        image_style="fotorealistisch",
    )
    result = graph.run("Erstelle bitte nur ein Bild dazu.", "post-img-tool")
    assert "ImageAgent" in (result.get("used_agents") or [])
    image = (result.get("generated_artifacts") or {}).get("image") or {}
    assert "get_post_data" in (image.get("tools_called") or [])
    # Prompt path should have seen image_context via enrich (FakeHF generate captures user prompts)
    joined = " ".join(hf.user_prompts).lower()
    assert "image_context" in joined or "flaggen" in joined or "spieler" in joined


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


def test_keyword_only_asks_before_generate():
    """Bare text/image keywords without erstell/schreib → ask, do not auto-run agents."""
    from app.agents.manager_agent import ManagerIntentClassifier

    clf = ManagerIntentClassifier()

    ambiguous_image = clf.classify_intent("Ein Bild mit zwei Spielern und Flaggen.")
    assert ambiguous_image.label == "clarification_needed"
    assert ambiguous_image.use_image is False

    ambiguous_text = clf.classify_intent("LinkedIn Post über die Nationalmannschaft")
    assert ambiguous_text.label == "clarification_needed"
    assert ambiguous_text.use_text is False

    explicit = clf.classify_intent("Erstelle bitte ein Bild mit zwei Spielern und Flaggen.")
    assert explicit.label == "image_only"
    assert explicit.use_image is True

    explicit_text = clf.classify_intent("Schreibe einen LinkedIn Post über die Nationalmannschaft.")
    assert explicit_text.label == "text_only"
    assert explicit_text.use_text is True

    # Explicit scope phrases remain direct even without erstell/schreib.
    only_image = clf.classify_intent("Nur ein Bild bitte.")
    assert only_image.label == "image_only"


def test_keyword_only_graph_does_not_run_image_agent(tmp_path: Path):
    hf = FakeHF()
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=FakeRAG(""))
    seed_post(
        graph,
        "post-ask-first",
        topic="Fußball",
        platform="LinkedIn",
        target_audience="Fans",
        tone_of_voice="stolz",
        image_context="Zwei Spieler, Flaggen im Hintergrund",
        image_style="fotorealistisch",
    )
    result = graph.run("Ein Bild mit den WM-Gewinnern.", "post-ask-first")
    assert "ImageAgent" not in (result.get("used_agents") or [])
    assert "TextAgent" not in (result.get("used_agents") or [])
    message = (result.get("assistant_message") or "").lower()
    assert any(token in message for token in ("text", "bild", "beides", "soll ich"))
