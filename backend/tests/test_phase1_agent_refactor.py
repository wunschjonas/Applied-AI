from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.manager_agent import ManagerIntentClassifier
from app.graphs.manager_chat_graph import ManagerChatGraph
from app.core.config import settings
from app.main import app
from app.services.chat_service import ChatService
from app.services.huggingface_service import HuggingFaceService
from app.services.image_storage_service import ImageStorageService
from app.services.log_service import LogService
from app.services.trace_service import TraceService


class FakeHF:
    hf_model_id = "fake-text-model"
    hf_image_model_id = "fake-image-model"

    def __init__(self, image_failures: int = 0, short_text_failures: int = 0):
        self.image_failures = image_failures
        self.short_text_failures = short_text_failures
        self.user_prompts: list[str] = []
        self.tool_rounds: list[dict] = []
        self._rag_tool_used = False

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 700) -> str:
        self.user_prompts.append(user_prompt)
        # Brief extraction / manager dialogue: force static fallbacks in most tests.
        if "Return ONLY a JSON object" in system_prompt:
            return "{}"
        if "marketing manager agent" in system_prompt.lower():
            raise RuntimeError("FakeHF skips dynamic manager replies")
        if "production-ready image generation prompts" in system_prompt:
            return (
                "A cinematic wide-angle commercial photograph of a modern marketing team collaborating around "
                "a glowing holographic AI dashboard, soft daylight from large windows, teal and charcoal color "
                "palette, shallow depth of field, clean composition, premium brand aesthetic, no readable text."
            )
        if self.short_text_failures > 0:
            self.short_text_failures -= 1
            return "Too short"
        return (
            "AI agents are reshaping how marketing teams plan, create, and measure campaigns. "
            "Start with one high-impact workflow, measure the lift, then scale what works. "
            "Ready to put agents to work in your next campaign? Book a strategy session today. "
            "#AI #Marketing #Agents #Automation"
        )

    def chat_with_tools(self, messages, tools, max_tokens: int = 400, temperature: float = 0.2) -> dict:
        self.tool_rounds.append({"messages": messages, "tools": tools})
        # Only inspect user turns — the system prompt itself mentions PDFs/memory.
        combined = " ".join(
            str(item.get("content") or "")
            for item in messages
            if item.get("role") == "user"
        ).lower()
        should_search = (
            not self._rag_tool_used
            and ("pdf" in combined or "brand guidelines" in combined or "gedächtnis" in combined)
        )
        if should_search:
            self._rag_tool_used = True
            return {
                "content": "I should check project memory for the uploaded PDF.",
                "tool_calls": [
                    {
                        "id": "call_memory_1",
                        "name": "memory_search",
                        "arguments": {"query": "brand guidelines pdf", "n_results": 3},
                    }
                ],
            }
        return {"content": "No memory search needed.", "tool_calls": []}

    def describe_image(self, image_bytes: bytes) -> str:
        return "a marketing product photo on a clean desk"

    def generate_image(self, prompt: str, negative_prompt: str | None = None) -> bytes:
        if self.image_failures > 0:
            self.image_failures -= 1
            raise RuntimeError("HuggingFace image transient error: TimeoutError: temporary unavailable")
        return b"fake-png-bytes"


class FakeRAG:
    def __init__(self, result: str = "stored memory context"):
        self.retrieve_called = False
        self.search_queries: list[str] = []
        self.stored: list[tuple[str, list[str]]] = []
        self.result = result

    def is_needed(self, message: str) -> bool:
        return "pdf" in message.lower() or "brand guidelines" in message.lower()

    def search(self, query: str, n_results: int = 3) -> str:
        self.retrieve_called = True
        self.search_queries.append(query)
        return self.result

    def retrieve(self, query: str, context=None) -> str:
        return self.search(query)

    def store(self, content: str, tags: list[str] | None = None) -> None:
        self.stored.append((content, tags or []))

    def list_all(self) -> list[str]:
        return [content for content, _ in self.stored]


def build_graph(tmp_path: Path, hf_factory=None, rag_service=None) -> ManagerChatGraph:
    from app.core import config as config_module

    config_module.settings.chats_file = tmp_path / "chats.json"
    config_module.settings.traces_file = tmp_path / "traces.json"
    config_module.settings.agent_logs_file = tmp_path / "agent_logs.json"
    config_module.settings.posts_file = tmp_path / "posts.json"

    storage = ImageStorageService(tmp_path / "generated_images")
    return ManagerChatGraph(
        chat_service=ChatService(),
        trace_service=TraceService(),
        rag_service=rag_service or FakeRAG(""),
        hf_factory=hf_factory or (lambda: FakeHF()),
        log_service=LogService(),
        image_storage=storage,
    )


def seed_post(graph: ManagerChatGraph, post_id: str, **fields) -> dict:
    post = {
        "id": post_id,
        "title": "Testpost",
        "status": "draft",
        "topic": None,
        "platform": None,
        "target_audience": None,
        "tone_of_voice": None,
        "additional_context": None,
        "preview": None,
    }
    post.update(fields)
    return graph.post_repository.save(post)


def test_intent_classification_cases():
    classifier = ManagerIntentClassifier()
    assert classifier.classify_intent("Schreibe einen LinkedIn Post").label == "text_only"
    assert classifier.classify_intent("Erstelle ein Bild fuer Instagram").label == "image_only"
    assert classifier.classify_intent("Erstelle ein Bild. Nur das Bild!").label == "image_only"
    assert classifier.classify_intent("Instagram Caption mit Hashtags und Bildidee").label == "text_and_image"
    assert classifier.classify_intent("Ist im Gedaechtnis ein Bild?").label == "memory_inquiry"
    assert classifier.classify_intent("Was steht in deinem Rag / Gedaechtnis?").label == "memory_inquiry"
    assert classifier.classify_intent("Hilf mir bitte").label == "clarification_needed"


def test_graph_text_only_uses_only_text_agent(tmp_path):
    graph = build_graph(tmp_path)
    result = graph.run("Schreibe einen LinkedIn Post ueber KI-Agenten im Marketing.", "post-text")

    assert result["used_agents"] == ["TextAgent"]
    assert "text" in result["generated_artifacts"]
    assert "image" not in result["generated_artifacts"]
    assert result["trace_id"]


def test_graph_image_only_returns_image_artifact(tmp_path):
    post_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    graph = build_graph(tmp_path)
    result = graph.run("Erstelle ein Instagram Bild ueber AI Marketing. Nur das Bild!", post_id)

    image = result["generated_artifacts"]["image"]
    assert result["used_agents"] == ["ImageAgent"]
    assert image["image_filename"] == f"{post_id}.png"
    assert image["image_url"] == f"/generated-images/{post_id}.png"
    assert (tmp_path / "generated_images" / image["image_filename"]).exists()


def test_graph_combined_uses_both_agents(tmp_path):
    post_id = "11111111-2222-3333-4444-555555555555"
    graph = build_graph(tmp_path)
    result = graph.run("Erstelle eine Instagram Caption mit Hashtags und Bildidee.", post_id)

    assert result["used_agents"] == ["TextAgent", "ImageAgent"]
    assert "text" in result["generated_artifacts"]
    assert "image" in result["generated_artifacts"]
    assert result["generated_artifacts"]["image"]["image_filename"] == f"{post_id}.png"


def test_manager_delegates_separate_briefs_to_both_specialists(tmp_path):
    post_id = "22222222-3333-4444-5555-666666666666"
    hf = FakeHF()
    graph = build_graph(tmp_path, hf_factory=lambda: hf)
    result = graph.run("Erstelle eine Instagram Caption mit Hashtags und Bildidee.", post_id)

    trace = graph.trace_service.get_trace(result["trace_id"])
    plan_step = next(step for step in trace["steps"] if step["action"] == "create_plan")
    assert "Erstelle den Marketing-Text" in plan_step["observation"]
    assert "Erstelle das Bildmotiv" in plan_step["observation"]

    text_brief = next(prompt for prompt in hf.user_prompts if "Erstelle den Marketing-Text" in prompt)
    assert "Erstelle das Bildmotiv" not in text_brief


def test_image_brief_includes_generated_marketing_text(tmp_path):
    post_id = "33333333-4444-5555-6666-777777777777"
    hf = FakeHF()
    graph = build_graph(tmp_path, hf_factory=lambda: hf)
    result = graph.run("Erstelle eine Instagram Caption mit Hashtags und Bildidee.", post_id)

    marketing_text = result["generated_artifacts"]["text"]["generated_text"]
    image_brief = next(prompt for prompt in hf.user_prompts if "Erstelle das Bildmotiv" in prompt)
    assert "Bereits erstellter Marketing-Text" in image_brief
    assert marketing_text[:60] in image_brief


def test_image_only_brief_has_no_marketing_text_section(tmp_path):
    post_id = "44444444-5555-6666-7777-888888888888"
    hf = FakeHF()
    graph = build_graph(tmp_path, hf_factory=lambda: hf)
    graph.run("Erstelle ein Instagram Bild ueber AI Marketing. Nur das Bild!", post_id)

    image_brief = next(prompt for prompt in hf.user_prompts if "Erstelle das Bildmotiv" in prompt)
    assert "Bereits erstellter Marketing-Text" not in image_brief


def test_graph_clarification_uses_no_specialist(tmp_path):
    graph = build_graph(tmp_path)
    result = graph.run("Hilf mir bitte mit dem Projekt.", "post-clarify")

    assert result["used_agents"] == []
    assert result["generated_artifacts"] == {}
    assert "Marketing-Text" in result["assistant_message"]


def test_rag_request_executes_rag_path(tmp_path):
    rag = FakeRAG("brand guideline memory")
    graph = build_graph(tmp_path, rag_service=rag)
    result = graph.run("Schreibe einen LinkedIn Post basierend auf unserem PDF.", "post-rag")

    assert rag.retrieve_called
    assert result["used_agents"] == ["TextAgent"]


def test_text_validation_retries_once(tmp_path):
    hf = FakeHF(short_text_failures=1)
    graph = build_graph(tmp_path, hf_factory=lambda: hf)
    result = graph.run("Schreibe einen LinkedIn Post ueber KI-Agenten.", "post-text-retry")

    assert result["generated_artifacts"]["text"]["generated_text"].startswith("AI agents")
    trace = graph.trace_service.get_trace(result["trace_id"])
    assert any(step["action"] == "retry_text" for step in trace["steps"])
    assert sum(1 for step in trace["steps"] if step["action"] == "retry_text") == 1


def test_image_generation_transient_failure_retries_once(tmp_path):
    post_id = "abcdef01-2345-6789-abcd-ef0123456789"
    hf = FakeHF(image_failures=1)
    graph = build_graph(tmp_path, hf_factory=lambda: hf)
    result = graph.run("Erstelle ein Bild fuer Instagram. Nur das Bild!", post_id)

    assert result["generated_artifacts"]["image"]["image_url"] == f"/generated-images/{post_id}.png"
    trace = graph.trace_service.get_trace(result["trace_id"])
    assert sum(1 for step in trace["steps"] if step["action"] == "retry_image") == 1


def test_image_prompt_partial_success_no_infinite_retry_for_permission(tmp_path):
    class PermissionHF(FakeHF):
        def generate_image(self, prompt: str, negative_prompt: str | None = None) -> bytes:
            raise RuntimeError("HuggingFace image permission denied: 403")

    graph = build_graph(tmp_path, hf_factory=lambda: PermissionHF())
    result = graph.run("Erstelle ein Bild fuer Instagram. Nur das Bild!", "post-image-partial")

    image = result["generated_artifacts"]["image"]
    assert image["image_prompt"]
    assert image["image_url"] is None
    trace = graph.trace_service.get_trace(result["trace_id"])
    assert not any(step["action"] == "retry_image" for step in trace["steps"])
    assert "fehlgeschlagen" in result["assistant_message"]


def test_chat_messages_have_role_and_content_only(tmp_path):
    from app.storage.json_store import JSONStore

    trace_file = tmp_path / "traces.json"
    trace_file.write_text("", encoding="utf-8")
    store = JSONStore(trace_file)
    assert store.list() == []
    assert trace_file.read_text(encoding="utf-8") == "[]"

    graph = build_graph(tmp_path)
    result = graph.run("Schreibe einen LinkedIn Post ueber KI-Agenten.", "post-metadata")
    chat = graph.chat_service.get_chat(result["chat_id"])
    last_message = chat["messages"][-1]
    assert set(last_message.keys()) == {"role", "content"}
    assert last_message["role"] == "AGENT"
    assert "metadata" not in last_message
    trace = graph.trace_service.get_trace(result["trace_id"])
    assert trace["metadata"]["trace_id"] == result["trace_id"]
    assert all("thought" in step and "action" in step and "observation" in step for step in trace["steps"])


def test_safe_filename_and_static_route_serves_test_image(tmp_path):
    storage = ImageStorageService(tmp_path)
    stored = storage.save_png(b"fake-png-bytes")
    assert storage.is_safe_filename(stored["image_filename"])
    assert storage.exists(stored["image_filename"])

    post_id = "99999999-aaaa-bbbb-cccc-dddddddddddd"
    named = storage.save_png(b"named-by-post", filename_stem=post_id)
    assert named["image_filename"] == f"{post_id}.png"
    assert storage.exists(named["image_filename"])

    static_storage = ImageStorageService(settings.generated_images_dir)
    static_stored = static_storage.save_png(b"static-test-bytes")
    client = TestClient(app)
    assert any(route.path == "/api/agents/image/generate" for route in app.routes if hasattr(route, "path"))
    response = client.get(static_stored["image_url"])
    assert response.status_code == 200
    assert response.content == b"static-test-bytes"


def test_huggingface_missing_token_readable_error():
    try:
        HuggingFaceService(hf_token=None, hf_model_id="text", hf_image_model_id="image")
    except ValueError as exc:
        assert "HF_TOKEN is missing" in str(exc)
    else:
        raise AssertionError("Missing token should raise a readable ValueError")
