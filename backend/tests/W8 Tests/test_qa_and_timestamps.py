from __future__ import annotations

from pathlib import Path

from app.graphs.support.manager_tools import sanitize_web_query
from app.graphs.support.post_fields import is_question_message
from app.services.log_service import LogService
from helpers import FakeHF, FakeRAG, build_graph, seed_post


PLATFORM_NUDGE = ("plattform", "linkedin", "instagram", "zielgruppe", "tonalitaet", "tonalität", "worum soll")


def test_log_timestamp_has_utc_offset(tmp_path: Path):
    from app.core import config as config_module

    config_module.settings.agent_logs_file = tmp_path / "agent_logs.json"
    logs = LogService()
    entry = logs.add_log(
        agent="manager",
        action="test",
        input_summary="offset check",
        status="success",
        duration_ms=1,
    )
    ts = entry["timestamp"]
    assert ts.endswith("+00:00") or ts.endswith("Z")
    assert "T" in ts


def test_sanitize_web_query_expands_pronoun_from_message():
    q = sanitize_web_query("wer", "Suche im Internet wer 2014 die WM gewonnen hat?")
    lowered = q.lower()
    assert "wer" not in lowered.split()[:1] or "2014" in lowered
    assert "2014" in lowered
    assert any(token in lowered for token in ("wm", "gewonnen", "fußball", "fussball", "weltmeister"))


def test_sanitize_web_query_strips_search_prefix():
    q = sanitize_web_query(
        "Suche im Internet Fußball WM 2014",
        "Suche im Internet Fußball WM 2014",
    )
    assert not q.lower().startswith("suche")
    assert "2014" in q


def test_question_message_detection():
    assert is_question_message("Weißt du wer 2014 die WM gewonnen hat?")
    assert is_question_message("Suche im Internet aktuelle KI Trends")
    assert not is_question_message("Schreibe einen LinkedIn Post zu KI Agents")


def test_knowledge_question_uses_memory_not_platform_ask(tmp_path: Path):
    """Tool-first: memory_search hit answers even if intent looks like clarification."""
    hf = FakeHF()
    rag = FakeRAG("Deutschland hat die Fußball-WM 2014 in Brasilien gewonnen.")
    graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=rag)
    seed_post(graph, "post-wm", topic="")  # empty Steckbrief on purpose

    result = graph.run("Weißt du wer 2014 die WM gewonnen hat?", "post-wm")
    message = (result.get("assistant_message") or "").lower()

    assert rag.retrieve_called
    assert "deutschland" in message or "2014" in message or "gewonnen" in message
    assert not any(marker in message for marker in PLATFORM_NUDGE)
    assert "TextAgent" not in (result.get("used_agents") or [])

    trace = graph.trace_service.get_trace(result["trace_id"])
    assert any(step.get("agent") == "memory_answer_node" for step in trace["steps"])
    actions = [step.get("action") or "" for step in trace["steps"]]
    assert any("memory_search" in a for a in actions)


def test_web_pronoun_query_sanitized_in_dispatch(tmp_path: Path):
    """Dispatcher rebuilds weak tool query 'wer' from the full user message."""
    hf = FakeHF()
    # Force FakeHF to emit a weak query once.
    original = FakeHF.chat_with_tools

    def weak_web_chat(self, messages, tools, max_tokens: int = 400, temperature: float = 0.2):
        self.tool_rounds.append({"messages": messages, "tools": tools})
        if not getattr(self, "_web_used", False):
            self._web_used = True
            return {
                "content": "Calling web_search.",
                "tool_calls": [
                    {
                        "id": "call_web_weak",
                        "name": "web_search",
                        "arguments": {"query": "wer", "max_results": 3},
                    }
                ],
            }
        return {"content": "No further tools needed.", "tool_calls": []}

    FakeHF.chat_with_tools = weak_web_chat
    try:
        graph = build_graph(tmp_path, hf_factory=lambda: hf, rag_service=FakeRAG(""))
        seen: list[str] = []

        def stub(q, max_results=3):
            seen.append(q)
            return "1. Deutschland gewann die WM 2014."

        graph.rag_nodes.dispatcher.web_search = stub
        seed_post(graph, "post-web-wer", topic="KI")

        result = graph.run(
            "Suche im Internet wer 2014 die WM gewonnen hat?",
            "post-web-wer",
        )
        assert seen, "web_search should have been called"
        query = seen[0].lower()
        assert query != "wer"
        assert "2014" in query
        message = (result.get("assistant_message") or "").lower()
        assert not any(marker in message for marker in ("zielgruppe", "worum soll", "welche tonal"))
        trace = graph.trace_service.get_trace(result["trace_id"])
        assert any(step.get("agent") == "web_answer_node" for step in trace["steps"])
    finally:
        FakeHF.chat_with_tools = original


def test_compose_rejects_chinese_drift():
    from app.graphs.support.post_data_llm import _ensure_german_reply

    german = "Die Mannschaft ist bekannt für starke Teamarbeit."
    mixed = german + "很深的哲学思考往往源于对生活"
    assert _ensure_german_reply(mixed, "Fallback DE") == "Fallback DE"
    assert _ensure_german_reply(german, "Fallback DE") == german
