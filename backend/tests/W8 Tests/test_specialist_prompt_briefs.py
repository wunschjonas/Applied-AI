from __future__ import annotations

from pathlib import Path

from app.agents.image_agent import ImageAgent
from app.agents.text_agent import TextAgent
from app.graphs.support.delegation import build_assignments, build_brief_section
from app.graphs.support.post_fields import normalize_text_length_guidance
from helpers import FakeHF, FakeRAG, build_graph, seed_post


def test_text_brief_excludes_image_fields():
    context = {
        "topic": "Fußball",
        "text_context": "WM-Sieger feiern",
        "text_length": "kurz",
        "image_context": "Zwei Spieler und Flaggen",
        "image_style": "fotorealistisch",
        "tone": "stolz",
    }
    text_brief = build_brief_section(context, for_agent="text")
    assert "Textkontext" in text_brief
    assert "Textlaenge" in text_brief or "Textlänge" in text_brief or "kurz" in text_brief
    assert "Bildmotiv" not in text_brief
    assert "Bildstil" not in text_brief

    image_brief = build_brief_section(context, for_agent="image")
    assert "Bildmotiv" in image_brief
    assert "Bildstil" in image_brief
    assert "Tonalitaet" in image_brief or "Mood" in image_brief or "stolz" in image_brief
    assert "Textkontext" not in image_brief
    assert "Textlaenge" not in image_brief


def test_assignments_use_split_briefs():
    context = {
        "topic": "KI",
        "tone": "professionell",
        "target_audience": "CMOs",
        "text_context": "Automation hilft Teams",
        "text_length": "mittel",
        "image_context": "Team am Dashboard",
        "image_style": "clean commercial",
    }
    assignments = build_assignments("text_and_image", "Erstelle Text und Bild.", context, "linkedin")
    assert "Bildmotiv" not in assignments["text"]["task"]
    assert "Textkontext" in assignments["text"]["task"]
    assert "Textkontext" not in assignments["image"]["task"]
    assert "Bildmotiv" in assignments["image"]["task"]
    assert assignments["image"].get("tone") == "professionell"


def test_normalize_text_length_guidance_maps_buckets():
    short = normalize_text_length_guidance("kurz bitte")
    assert short and "40-80" in short
    medium = normalize_text_length_guidance("medium")
    assert medium and "80-150" in medium
    long = normalize_text_length_guidance("lang")
    assert long and "150-250" in long
    custom = normalize_text_length_guidance("etwa eine Seite")
    assert custom and "etwa eine Seite" in custom


def test_text_agent_prompt_includes_hard_length():
    hf = FakeHF()
    agent = TextAgent(hf, trace_service=type("T", (), {"add_step": lambda *a, **k: None})())
    # Fake BaseAgent.record — use a minimal stub if needed
    trace = {"steps": []}

    class _Trace:
        def add_step(self, *args, **kwargs):
            return None

    agent.trace_service = _Trace()
    agent.generate(
        task="Schreibe einen Post",
        trace=trace,
        platform="linkedin",
        tone="professionell",
        target_audience="Fans",
        text_context="Kernbotschaft WM",
        text_length="kurz",
    )
    joined = " ".join(hf.user_prompts)
    assert "40-80" in joined
    assert "Length requirement" in joined or "mandatory" in joined.lower()


def test_image_agent_prompt_includes_tone(tmp_path: Path):
    hf = FakeHF()
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=FakeRAG(""))
    seed_post(
        graph,
        "post-tone-image",
        topic="Fußball WM",
        platform="LinkedIn",
        target_audience="Fans",
        tone_of_voice="stolz",
        image_context="Zwei WM-Gewinner im Duell, Flaggen im Hintergrund",
        image_style="fotorealistisch",
    )
    result = graph.run("Erstelle bitte nur ein Bild dazu.", "post-tone-image")
    assert "ImageAgent" in (result.get("used_agents") or [])
    joined = " ".join(hf.user_prompts).lower()
    assert "stolz" in joined or "tone" in joined or "mood" in joined
