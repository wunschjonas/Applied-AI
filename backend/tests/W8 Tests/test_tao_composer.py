from __future__ import annotations

from app.graphs.support.tao_composer import TaoEvent, compose


def test_compose_same_phase_different_facts_differs():
    a = compose(
        TaoEvent(
            phase="rag_search",
            node="rag_react_node",
            facts={
                "rag_mode": "llm",
                "query": "Fußball WM",
                "rag_hit_count": 1,
                "rag_summary": "Deutschland hat 2014 die WM gewonnen",
            },
        )
    )
    b = compose(
        TaoEvent(
            phase="rag_search",
            node="rag_react_node",
            facts={
                "rag_mode": "forced",
                "query": "Aliens",
                "rag_hit_count": 2,
                "rag_summary": "Aliens haben blaue Haut",
            },
        )
    )
    assert a.thought and a.action and a.observation
    assert b.thought and b.observation
    assert a.observation != b.observation
    assert "Fußball" in a.action or "Fußball" in a.thought or "Fußball" in a.observation
    assert "Aliens" in b.action or "Aliens" in b.thought or "Aliens" in b.observation


def test_compose_intent_changes_plan_observation():
    text_only = compose(
        TaoEvent(
            phase="create_plan",
            node="create_plan_node",
            intent="text_only",
            facts={
                "required_agents": ["TextAgent"],
                "expected_artifacts": ["text"],
                "needs_rag_check": False,
            },
        )
    )
    both = compose(
        TaoEvent(
            phase="create_plan",
            node="create_plan_node",
            intent="text_and_image",
            facts={
                "required_agents": ["TextAgent", "ImageAgent"],
                "expected_artifacts": ["text", "image"],
                "needs_rag_check": True,
            },
        )
    )
    assert "TextAgent" in text_only.observation
    assert "ImageAgent" in both.observation
    assert text_only.observation != both.observation


def test_compose_tool_error_and_validation_retry_visible():
    err = compose(
        TaoEvent(
            phase="manager_tool",
            node="rag_react_node",
            status="error",
            facts={
                "tool_name": "web_search",
                "tool_error": "web_search unavailable (disabled or not configured)",
                "query": "trends",
            },
        )
    )
    assert "Fehler" in err.action or "fehlgeschlagen" in err.thought.lower()
    assert "unavailable" in err.observation.lower() or "web_search" in err.observation.lower()

    incomplete = compose(
        TaoEvent(
            phase="manager_tool",
            node="rag_react_node",
            status="warning",
            facts={
                "tool_name": "check_post_data_completeness",
                "post_data_complete": False,
                "post_data_missing": ["tone_of_voice", "target_audience"],
            },
        )
    )
    assert incomplete.action == "check_post_data_completeness"
    assert "tone_of_voice" in incomplete.observation

    retry = compose(
        TaoEvent(
            phase="retry",
            node="validation_node",
            status="retry_text",
            facts={"artifact_type": "text", "agent_label": "TextAgent", "feedback": "text too short"},
        )
    )
    assert "Validation-Retry" in retry.action
    assert "TextAgent" in retry.thought or "TextAgent" in retry.observation


def test_compose_post_data_safety_net():
    safety = compose(
        TaoEvent(
            phase="post_data_safety",
            node="route_by_intent",
            status="needs_input",
            facts={
                "detail": "Safety: Steckbrief unvollständig, Generierung blockiert.",
                "post_data_missing": ["topic"],
            },
        )
    )
    assert "Safety" in safety.thought or "post_data_safety" in safety.action
    assert "topic" in safety.observation or "blockiert" in safety.observation.lower()


def test_compose_never_empty_and_clips_long_summary():
    long = "x" * 500
    triple = compose(
        TaoEvent(
            phase="rag_search",
            node="rag_react_node",
            facts={"rag_mode": "llm", "query": "test", "rag_summary": long, "rag_hit_count": 1},
        )
    )
    assert triple.thought.strip()
    assert triple.action.strip()
    assert triple.observation.strip()
    assert len(triple.observation) <= 320
    assert "Let's think step by step" not in triple.thought
    assert "<think>" not in triple.thought.lower()


def test_compose_unknown_phase_fallback():
    triple = compose(
        TaoEvent(
            phase="totally_unknown_phase",
            node="some_node",
            intent="text_only",
            facts={"detail": "runtime detail here"},
        )
    )
    assert "some_node" in triple.thought or "totally_unknown" in triple.thought
    assert triple.observation
