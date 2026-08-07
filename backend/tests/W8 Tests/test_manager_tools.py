from __future__ import annotations

from app.graphs.support.manager_tools import ManagerToolDispatcher


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
