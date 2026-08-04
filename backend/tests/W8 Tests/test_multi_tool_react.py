from __future__ import annotations

from pathlib import Path

from helpers import FakeHF, FakeRAG, build_graph, seed_post


def test_different_inputs_produce_different_tool_actions(tmp_path: Path):
    """Dim-2: traces must show situation-dependent tool choice."""

    def run(message: str, post_id: str, hf: FakeHF, rag: FakeRAG, folder: Path):
        graph = build_graph(folder, hf_factory=lambda: hf, rag_service=rag)
        seed_post(
            graph,
            post_id,
            topic="KI Agenten",
            platform="LinkedIn",
            target_audience="CMOs",
            tone_of_voice="professionell",
        )
        result = graph.run(message, post_id)
        trace = graph.trace_service.get_trace(result["trace_id"])
        actions = [step.get("action") or "" for step in trace["steps"]]
        return actions, result

    hf_mem = FakeHF()
    actions_mem, _ = run(
        "Schreibe einen LinkedIn Post basierend auf unserem PDF mit Brand Guidelines.",
        "post-tools-mem",
        hf_mem,
        FakeRAG("brand guideline memory"),
        tmp_path / "mem",
    )

    hf_web = FakeHF()
    actions_web, _ = run(
        "Schreibe einen LinkedIn Post zu aktuellen KI Trends heute.",
        "post-tools-web",
        hf_web,
        FakeRAG(""),
        tmp_path / "web",
    )

    hf_list = FakeHF()
    actions_list, _ = run(
        "Was weisst du im Gedaechtnis ueber Aliens?",
        "post-tools-list",
        hf_list,
        FakeRAG("Aliens fahren rote Autos"),
        tmp_path / "list",
    )

    assert any("check_post_data_completeness" in a for a in actions_mem)
    assert any("memory_search" in a for a in actions_mem)

    assert any("web_search" in a for a in actions_web)
    # Research-first: web_search without forcing completeness in the same tool loop

    assert any("memory_list" in a for a in actions_list)

    # Sequences must differ across scenarios
    assert actions_mem != actions_web
    assert actions_web != actions_list


def test_incomplete_brief_uses_completeness_tool(tmp_path: Path):
    hf = FakeHF()
    rag = FakeRAG("")
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=rag)
    seed_post(graph, "post-incomplete", topic="Nur Thema")  # missing other required fields

    result = graph.run("Schreibe bitte einen LinkedIn Post.", "post-incomplete")
    trace = graph.trace_service.get_trace(result["trace_id"])
    actions = [step.get("action") or "" for step in trace["steps"]]

    assert any("check_post_data_completeness" in a for a in actions)
    assert "TextAgent" not in (result.get("used_agents") or [])
    assert result.get("assistant_message")


def test_memory_store_on_explicit_user_request(tmp_path: Path):
    hf = FakeHF()
    rag = FakeRAG("")
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=rag)
    seed_post(
        graph,
        "post-store",
        topic="Brand",
        platform="LinkedIn",
        target_audience="CMOs",
        tone_of_voice="klar",
    )
    result = graph.run(
        "Merk dir bitte: Unsere Markenfarbe ist Petrolblau.",
        "post-store",
    )
    trace = graph.trace_service.get_trace(result["trace_id"])
    actions = [step.get("action") or "" for step in trace["steps"]]
    assert any("memory_store" in a for a in actions)
    assert rag.stored
    assert any("Petrolblau" in content for content, _ in rag.stored)


def test_memory_store_uses_previous_chat_fact(tmp_path: Path):
    hf = FakeHF()
    rag = FakeRAG("")
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=rag)
    seed_post(
        graph,
        "post-store-prior",
        topic="Brand",
        platform="LinkedIn",
        target_audience="CMOs",
        tone_of_voice="klar",
    )
    fact = (
        "Die deutsche Nationalmannschaft hat eine lange und ehrenvolle Geschichte im Fußball. "
        "Ihr Erfolg erstreckt sich über mehrere Jahrzehnte."
    )
    graph.run(fact, "post-store-prior")
    result = graph.run("Speicher den Fakt im Rag ab", "post-store-prior")
    trace = graph.trace_service.get_trace(result["trace_id"])
    actions = [step.get("action") or "" for step in trace["steps"]]
    assert any("memory_store" in a for a in actions)
    assert any("Nationalmannschaft" in content for content, _ in rag.stored)
    assert not any("Fakt im Rag" == content.strip() for content, _ in rag.stored)
    message = (result.get("assistant_message") or "").lower()
    assert "gespeichert" in message or "gemerkt" in message or "rag" in message
    assert "keine passenden" not in message
    assert any(step.get("agent") == "memory_store_ack_node" for step in trace["steps"])
    # Topical tags instead of only manager_store
    assert rag.stored
    tags = rag.stored[-1][1]
    assert tags
    assert "manager_store" not in tags or len(tags) > 1
    assert any("fussball" in t or "nationalmannschaft" in t for t in tags)


def test_web_error_observation_then_memory_fallback_path(tmp_path: Path):
    """When web_search fails, observation stays visible; follow-up can use memory."""
    from app.core import config as config_module

    config_module.settings.web_search_enabled = False
    hf = FakeHF()
    rag = FakeRAG("interne Marken-Guidelines zu KI")
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=rag)
    seed_post(
        graph,
        "post-web-err",
        topic="KI Trends",
        platform="LinkedIn",
        target_audience="CMOs",
        tone_of_voice="professionell",
    )
    # Force web first via FakeHF keywords, then completeness/memory on later rounds
    result = graph.run(
        "Schreibe einen LinkedIn Post zu aktuellen KI Trends heute basierend auf PDF Brand Guidelines.",
        "post-web-err",
    )
    trace = graph.trace_service.get_trace(result["trace_id"])
    actions = [step.get("action") or "" for step in trace["steps"]]
    # FakeHF prefers web for "aktuell/heute", then completeness for generate
    assert any("web_search" in a for a in actions)
    # Error path should mark web_search as Fehler or show error observation
    web_steps = [s for s in trace["steps"] if "web_search" in (s.get("action") or "")]
    assert web_steps
    assert any(
        "Fehler" in (s.get("action") or "")
        or "unavailable" in (s.get("observation") or "").lower()
        or "fehlgeschlagen" in (s.get("thought") or "").lower()
        for s in web_steps
    )
    assert result.get("trace_id")


def test_forced_memory_store_when_hf_tools_fail(tmp_path: Path):
    """When HF tool-calling fails, memory_store still runs via forced fallback."""

    class BrokenToolsHF(FakeHF):
        def chat_with_tools(self, messages, tools, max_tokens: int = 400, temperature: float = 0.2) -> dict:
            raise RuntimeError(
                "HuggingFace tool request failed: BadRequestError: Bad request"
            )

    hf = BrokenToolsHF()
    rag = FakeRAG("")
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=rag)
    seed_post(graph, "post-forced-store")  # incomplete Steckbrief on purpose

    result = graph.run(
        "Merk dir: Spanien hat die WM 2026 gewonnen",
        "post-forced-store",
    )
    trace = graph.trace_service.get_trace(result["trace_id"])
    actions = [step.get("action") or "" for step in trace["steps"]]

    assert any("memory_store" in a for a in actions)
    assert rag.stored
    assert any("Spanien" in content and "2026" in content for content, _ in rag.stored)
    assert any(step.get("agent") == "memory_store_ack_node" for step in trace["steps"])

    message = (result.get("assistant_message") or "").lower()
    assert "gespeichert" in message or "gemerkt" in message or "rag" in message
    assert "worum soll der post" not in message
    assert result.get("followup_question") in (None, "")
