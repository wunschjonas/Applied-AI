from __future__ import annotations

from app.graphs.support.manager_tools import MANAGER_TOOL_NAMES, ManagerToolDispatcher


class _FakeRAG:
    def __init__(self):
        self.stored: list[tuple[str, list[str]]] = []
        self.searches: list[str] = []

    def search(self, query: str, n_results: int = 3) -> str:
        self.searches.append(query)
        return "Brand color is blue"

    def list_all(self) -> list[str]:
        return [c for c, _ in self.stored] or ["Existing memory fact about football"]

    def store(self, content: str, tags: list[str] | None = None) -> None:
        self.stored.append((content, tags or []))


class _FakePosts:
    def get(self, post_id: str):
        return {
            "id": post_id,
            "topic": "Fußball",
            "platform": "linkedin",
            "target_audience": "Fans",
            "tone_of_voice": "sportlich",
            "preview": {"generated_text": "Hallo"},
        }


def _dispatcher(web=None) -> ManagerToolDispatcher:
    return ManagerToolDispatcher(
        rag_service=_FakeRAG(),
        post_repository=_FakePosts(),
        web_search=web,
    )


def test_manager_tool_names_cover_plan_set():
    assert MANAGER_TOOL_NAMES == {
        "memory_search",
        "memory_list",
        "memory_store",
        "web_search",
        "get_post_data",
        "check_post_data_completeness",
    }


def test_dispatch_memory_search_and_list():
    d = _dispatcher()
    state: dict = {"user_message": "brand color", "post": {"topic": "brand"}}
    obs, status, effects = d.dispatch("memory_search", {"query": "brand color"}, state)
    assert status == "success"
    assert effects.get("rag_needed")
    assert effects.get("rag_hit_count", 0) >= 1

    obs2, status2, _ = d.dispatch("memory_list", {}, state)
    assert status2 == "success"
    assert len(obs2) > 10


def test_dispatch_memory_store():
    d = _dispatcher()
    obs, status, effects = d.dispatch(
        "memory_store",
        {"content": "Deutschland wurde 2014 Weltmeister", "tags": ["fussball"]},
        {},
    )
    assert status == "success"
    assert "Stored" in obs or "gespeichert" in obs.lower() or "chars" in obs
    assert d.rag.stored


def test_suggest_memory_tags_are_topical():
    from app.graphs.support.manager_tools import suggest_memory_tags

    tags = suggest_memory_tags(
        "Spanien gewann die Fußball-Weltmeisterschaft 2026 im Finale gegen Argentinien.",
        ["manager_store"],
    )
    assert "manager_store" not in tags
    assert "fussball_wm" in tags or "fussball" in tags
    assert "spanien" in tags


def test_memory_store_resolves_prior_user_fact():
    from app.graphs.support.manager_tools import resolve_memory_store_content

    prior = (
        "Die deutsche Nationalmannschaft hat eine lange und ehrenvolle Geschichte im Fußball. "
        "Ihr Erfolg erstreckt sich über mehrere Jahrzehnte."
    )
    chat = {"messages": [{"role": "USER", "content": prior}]}
    resolved = resolve_memory_store_content(
        "den Fakt im Rag",
        user_message="Speicher den Fakt im Rag ab",
        chat=chat,
    )
    assert "Nationalmannschaft" in resolved
    assert "Fakt im Rag" not in resolved

    d = _dispatcher()
    obs, status, effects = d.dispatch(
        "memory_store",
        {"content": "den Fakt im Rag"},
        {"user_message": "Speicher den Fakt im Rag ab", "chat": chat},
    )
    assert status == "success"
    assert "Nationalmannschaft" in d.rag.stored[0][0]
    assert "Nationalmannschaft" in (effects.get("stored_preview") or "")


def test_dispatch_web_search_and_error_fallback_message():
    d = _dispatcher(web=lambda q, max_results=3: f"1. Result about {q}")
    obs, status, effects = d.dispatch("web_search", {"query": "KI Trends 2026"}, {})
    assert status == "success"
    assert "KI Trends" in obs
    assert effects.get("web_context")

    d2 = _dispatcher(web=None)
    obs2, status2, _ = d2.dispatch("web_search", {"query": "x"}, {})
    assert status2 == "error"
    assert "unavailable" in obs2.lower() or "memory_search" in obs2


def test_dispatch_brief_tools():
    d = _dispatcher()
    complete_post = {
        "topic": "A",
        "platform": "linkedin",
        "target_audience": "B",
        "tone_of_voice": "C",
        "text_context": "Kernbotschaft",
        "text_length": "kurz",
        "image_context": "Motiv",
        "image_style": "foto",
    }
    obs, status, effects = d.dispatch(
        "check_post_data_completeness",
        {},
        {"post": complete_post, "intent": "text_and_image"},
    )
    assert status == "success"
    assert effects.get("post_data_complete") is True

    obs2, status2, effects2 = d.dispatch(
        "check_post_data_completeness",
        {},
        {"post": {"topic": "A"}, "intent": "text_only"},
    )
    assert status2 == "warning"
    assert effects2.get("post_data_complete") is False
    assert "text_context" in (effects2.get("post_data_missing") or [])

    obs3, status3, _ = d.dispatch("get_post_data", {}, {"post_id": "p1", "post": None})
    assert status3 == "success"
    assert "Fußball" in obs3 or "linkedin" in obs3.lower() or "Brief" in obs3 or "post" in obs3.lower()
