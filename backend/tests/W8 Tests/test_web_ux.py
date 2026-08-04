from __future__ import annotations

from pathlib import Path

from helpers import FakeHF, FakeRAG, build_graph, seed_post


BRIEF_NUDGE_MARKERS = (
    "zielgruppe",
    "tonalität",
    "tonalitaet",
    "plattform",
    "worum soll",
    "wen willst",
    "welche tonal",
    "brief",
    "noch offen",
)


def _stub_web(graph) -> None:
    graph.rag_nodes.dispatcher.web_search = (
        lambda q, max_results=3: "1. Fake KI-Trend 2026: Agenten automatisieren Kampagnenplanung."
    )


def test_pure_web_inquiry_returns_search_only(tmp_path: Path):
    hf = FakeHF()
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=FakeRAG(""))
    _stub_web(graph)
    seed_post(graph, "post-web-pure", topic="KI")

    result = graph.run("Was sind aktuelle KI Trends heute?", "post-web-pure")
    message = (result.get("assistant_message") or "").lower()

    assert result.get("used_agents") == []
    assert "zusammengefasst" in message or "kernpunkt" in message or "fake ki-trend" in message
    assert "hier die aktuellen web-treffer" not in message
    assert not any(marker in message for marker in BRIEF_NUDGE_MARKERS)

    trace = graph.trace_service.get_trace(result["trace_id"])
    actions = [step.get("action") or "" for step in trace["steps"]]
    assert any("web_search" in a for a in actions)
    assert any("Web-Antwort" in a or "web_answer" in (step.get("agent") or "") for a, step in zip(actions, trace["steps"]) ) or any(
        step.get("agent") == "web_answer_node" for step in trace["steps"]
    )


def test_generate_with_trends_shows_web_not_brief_question(tmp_path: Path):
    """Generate wording + trends → web_search this turn; chat is results, not context_question."""
    hf = FakeHF()
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=FakeRAG(""))
    _stub_web(graph)
    seed_post(graph, "post-web-gen", topic="Nur Thema")  # incomplete brief on purpose

    result = graph.run(
        "Schreibe einen LinkedIn Post zu aktuellen KI Trends heute.",
        "post-web-gen",
    )
    message = (result.get("assistant_message") or "").lower()

    assert "TextAgent" not in (result.get("used_agents") or [])
    assert "zusammengefasst" in message or "kernpunkt" in message or "fake ki-trend" in message
    assert "hier die aktuellen web-treffer" not in message
    assert "wen willst" not in message
    assert "welche tonal" not in message

    trace = graph.trace_service.get_trace(result["trace_id"])
    actions = [step.get("action") or "" for step in trace["steps"]]
    assert any("web_search" in a for a in actions)
    assert not any("Steckbrief-Frage" in a for a in actions)
    assert any(step.get("agent") == "web_answer_node" for step in trace["steps"])
