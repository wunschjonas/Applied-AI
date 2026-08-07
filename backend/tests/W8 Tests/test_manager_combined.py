from __future__ import annotations

from pathlib import Path

from helpers import build_graph, run_generation, seed_post


def test_graph_combined_uses_both_agents(tmp_path: Path):
    post_id = "11111111-2222-3333-4444-555555555555"
    graph = build_graph(tmp_path)
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
    ack = graph.run("Erstelle eine Instagram Caption mit Hashtags und Bildidee.", post_id)
    assert ack["generation_pending"] is True
    assert ack["used_agents"] == []
    assert "informationen" in ack["assistant_message"].lower() or "generier" in ack["assistant_message"].lower()

    result = run_generation(graph, post_id)
    assert result["generation_pending"] is False
    assert result["used_agents"] == ["TextAgent", "ImageAgent"]
    assert "text" in result["generated_artifacts"]
    assert "image" in result["generated_artifacts"]
    assert result["generated_artifacts"]["image"]["image_filename"] == f"{post_id}.png"

    done = (result.get("assistant_message") or "").lower()
    assert len(done) < 420
    assert any(marker in done for marker in ("fertig", "text-agent", "image-agent", "vorschau"))
    assert "halt dich immer" not in done
    assert done.count('"') < 2 and "„" not in done


def test_brief_complete_auto_ack_then_generate(tmp_path: Path):
    """Filling the last Steckbrief field acks immediately; specialists run on generate."""
    post_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    graph = build_graph(tmp_path)
    seed_post(
        graph,
        post_id,
        topic="Firmenevent Lehrer",
        platform="linkedin",
        target_audience="Lehrer",
        tone_of_voice=None,
        text_context="Einladung zu einem Firmenevent fuer Lehrer.",
        text_length="mittel",
        image_context="Freundliche Lehrkraefte bei einem Empfang",
        image_style="fotorealistisch",
        awaiting_field="tone_of_voice",
    )
    ack = graph.run("aufgeschlossen", post_id)
    post = graph.post_repository.get(post_id)
    assert post.get("tone_of_voice")
    assert ack["generation_pending"] is True
    assert "TextAgent" not in (ack.get("used_agents") or [])

    result = run_generation(graph, post_id)
    assert result["used_agents"] == ["TextAgent", "ImageAgent"]


def test_welcome_message_has_no_content_sketch():
    from app.graphs.support.post_data_llm import welcome_message

    text = welcome_message("Pferdepflege", hf=None).casefold()
    assert "pferdepflege" in text
    assert "skizze" not in text
    assert "skizzenbild" not in text
    assert "inhalt skizz" not in text


def test_marketing_paste_guard_rejects_long_quoted_copy():
    from app.graphs.nodes.response import _looks_like_marketing_paste

    short = "Text und Bild sind fertig. Schau sie in der Vorschau an."
    assert _looks_like_marketing_paste(short) is False

    long_quote = (
        'Die Kombination ist perfekt! Hier ist ein Vorschlag: '
        '"Halt dich immer im Spiegel deines Pferdes! In jedem Tag der Versorgung '
        "liegt ein Stück Hingabe. Von der richtigen Fütterung bis hin zur täglichen "
        'Stallpflege." Was denkst du?'
    )
    assert _looks_like_marketing_paste(long_quote) is True
