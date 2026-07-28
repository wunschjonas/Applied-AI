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

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 700) -> str:
        if "production-ready image generation prompts" in system_prompt:
            return "A detailed modern marketing image prompt with clear subject, composition, lighting and colors."
        if self.short_text_failures > 0:
            self.short_text_failures -= 1
            return "Too short"
        return "A useful LinkedIn marketing post about AI agents in marketing with a clear CTA. #AI #Marketing #Agents"

    def generate_image(self, prompt: str, negative_prompt: str | None = None) -> bytes:
        if self.image_failures > 0:
            self.image_failures -= 1
            raise RuntimeError("HuggingFace image transient error: TimeoutError: temporary unavailable")
        return b"fake-png-bytes"


class FakeRAG:
    def __init__(self, result: str = "stored memory context"):
        self.retrieve_called = False
        self.result = result

    def is_needed(self, message: str) -> bool:
        return "pdf" in message.lower() or "brand guidelines" in message.lower()

    def retrieve(self, query: str, context=None) -> str:
        self.retrieve_called = True
        return self.result


def build_graph(tmp_path: Path, hf_factory=None, rag_service=None) -> ManagerChatGraph:
    from app.core import config as config_module

    config_module.settings.chats_file = tmp_path / "chats.json"
    config_module.settings.traces_file = tmp_path / "traces.json"
    config_module.settings.agent_logs_file = tmp_path / "agent_logs.json"

    storage = ImageStorageService(tmp_path / "generated_images")
    return ManagerChatGraph(
        chat_service=ChatService(),
        trace_service=TraceService(),
        rag_service=rag_service or FakeRAG(""),
        hf_factory=hf_factory or (lambda: FakeHF()),
        log_service=LogService(),
        image_storage=storage,
    )


def test_intent_classification_cases():
    classifier = ManagerIntentClassifier()
    assert classifier.classify_intent("Schreibe einen LinkedIn Post").label == "text_only"
    assert classifier.classify_intent("Erstelle ein Bild fuer Instagram").label == "image_only"
    assert classifier.classify_intent("Erstelle ein Bild. Nur das Bild!").label == "image_only"
    assert classifier.classify_intent("Instagram Caption mit Hashtags und Bildidee").label == "text_and_image"
    assert classifier.classify_intent("Hilf mir bitte").label == "clarification_needed"


def test_graph_text_only_uses_only_text_agent(tmp_path):
    graph = build_graph(tmp_path)
    result = graph.run("Schreibe einen LinkedIn Post ueber KI-Agenten im Marketing.", "post-text")

    assert result["used_agents"] == ["TextAgent"]
    assert "text" in result["generated_artifacts"]
    assert "image" not in result["generated_artifacts"]
    assert result["trace_id"]


def test_graph_image_only_returns_image_artifact(tmp_path):
    graph = build_graph(tmp_path)
    result = graph.run("Erstelle ein Instagram Bild ueber AI Marketing. Nur das Bild!", "post-image")

    image = result["generated_artifacts"]["image"]
    assert result["used_agents"] == ["ImageAgent"]
    assert image["image_url"].startswith("/generated-images/")
    assert image["image_filename"].endswith(".png")
    assert (tmp_path / "generated_images" / image["image_filename"]).exists()


def test_graph_combined_uses_both_agents(tmp_path):
    graph = build_graph(tmp_path)
    result = graph.run("Erstelle eine Instagram Caption mit Hashtags und Bildidee.", "post-combined")

    assert result["used_agents"] == ["TextAgent", "ImageAgent"]
    assert "text" in result["generated_artifacts"]
    assert "image" in result["generated_artifacts"]


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

    assert result["generated_artifacts"]["text"]["generated_text"].startswith("A useful")
    trace = graph.trace_service.get_trace(result["trace_id"])
    assert any(step["action"] == "retry_text" for step in trace["steps"])
    assert sum(1 for step in trace["steps"] if step["action"] == "retry_text") == 1


def test_image_generation_transient_failure_retries_once(tmp_path):
    hf = FakeHF(image_failures=1)
    graph = build_graph(tmp_path, hf_factory=lambda: hf)
    result = graph.run("Erstelle ein Bild fuer Instagram. Nur das Bild!", "post-image-retry")

    assert result["generated_artifacts"]["image"]["image_url"]
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


def test_chat_metadata_and_trace_file_initialization(tmp_path):
    from app.storage.json_store import JSONStore

    trace_file = tmp_path / "traces.json"
    trace_file.write_text("", encoding="utf-8")
    store = JSONStore(trace_file)
    assert store.list() == []
    assert trace_file.read_text(encoding="utf-8") == "[]"

    graph = build_graph(tmp_path)
    result = graph.run("Schreibe einen LinkedIn Post ueber KI-Agenten.", "post-metadata")
    chat = graph.chat_service.get_chat(result["chat_id"])
    assert "metadata" in chat["messages"][-1]
    assert chat["messages"][-1]["metadata"]["trace_id"] == result["trace_id"]


def test_safe_filename_and_static_route_serves_test_image(tmp_path):
    storage = ImageStorageService(tmp_path)
    stored = storage.save_png(b"fake-png-bytes")
    assert storage.is_safe_filename(stored["image_filename"])
    assert storage.exists(stored["image_filename"])

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
