from __future__ import annotations

from pathlib import Path

from app.graphs.manager_chat_graph import ManagerChatGraph
from app.services.agent_service import AgentService
from app.services.chat_service import ChatService
from app.services.image_storage_service import ImageStorageService
from app.services.log_service import LogService
from app.services.trace_service import TraceService


class FakeHF:
    hf_model_id = "fake-text-model"
    hf_image_model_id = "fake-image-model"
    hf_image_to_image_model_id = "fake-img2img-model"

    def __init__(
        self,
        image_failures: int = 0,
        short_text_failures: int = 0,
    ):
        self.image_failures = image_failures
        self.short_text_failures = short_text_failures
        self.user_prompts: list[str] = []
        self.tool_rounds: list[dict] = []
        self.img2img_calls: list[dict] = []
        self._rag_tool_used = False

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 700) -> str:
        self.user_prompts.append(user_prompt)
        if "Return ONLY a JSON object" in system_prompt:
            return "{}"
        if "marketing manager agent" in system_prompt.lower():
            raise RuntimeError("FakeHF skips dynamic manager replies")
        if "marketing text agent" in system_prompt.lower() or "marketing image agent" in system_prompt.lower():
            raise RuntimeError("FakeHF skips dynamic specialist replies")
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
        combined = " ".join(
            str(item.get("content") or "")
            for item in messages
            if item.get("role") in {"user", "tool"}
        ).lower()
        # Also include the planner user prompt (brief snapshot) from last user message only once
        user_bits = " ".join(
            str(item.get("content") or "")
            for item in messages
            if item.get("role") == "user"
        ).lower()

        available = set()
        for tool in tools or []:
            name = (tool.get("function") or {}).get("name")
            if name:
                available.add(name)

        def _call(name: str, arguments: dict) -> dict:
            return {
                "content": f"Calling {name}.",
                "tool_calls": [{"id": f"call_{name}_{len(self.tool_rounds)}", "name": name, "arguments": arguments}],
            }

        # ImageAgent / single-tool Steckbrief read (do not steal manager multi-tool rounds)
        if available == {"get_post_data"}:
            if not getattr(self, "_post_data_read", False):
                self._post_data_read = True
                return _call("get_post_data", {})

        # Explicit store request
        if any(k in user_bits for k in ("merk dir", "speicher", "remember", "save this", "store this")):
            if not getattr(self, "_store_used", False) and "memory_store" in available:
                self._store_used = True
                # Intentionally thin content — dispatcher must resolve from prior USER turn when needed.
                return _call("memory_store", {"content": "den Fakt im Rag", "tags": ["test"]})

        # Web / current events — prefer before completeness (research-first turn).
        web_like = any(
            k in user_bits
            for k in (
                "web",
                "internet",
                "aktuell",
                "trend",
                "nachrichten",
                "heute",
                "news",
                "recherchier",
            )
        )
        if web_like:
            if not getattr(self, "_web_used", False) and "web_search" in available:
                self._web_used = True
                return _call(
                    "web_search",
                    {"query": "Fußball Weltmeisterschaft 2014 Gewinner", "max_results": 3},
                )

        # Factual knowledge questions → memory_search (LLM tool choice path in tests).
        knowledge_like = any(
            k in user_bits
            for k in ("weißt du", "weisst du", "kennst du", "gewonnen", "wer hat", "wer war")
        )
        if knowledge_like and not web_like:
            if not self._rag_tool_used and "memory_search" in available:
                self._rag_tool_used = True
                return _call("memory_search", {"query": "WM 2014 Fußball Gewinner", "n_results": 3})

        # Memory overview questions
        if any(k in user_bits for k in ("gedächtnis", "gedaechtnis", "was weisst", "was weißt", "memory list")):
            if not getattr(self, "_list_used", False) and "memory_list" in available:
                self._list_used = True
                return _call("memory_list", {"limit": 10})

        # Generation path: completeness first, then optional memory_search for PDF/brand
        # Skip completeness for pure store intents ("merk dir …") and pure web research.
        store_like = any(k in user_bits for k in ("merk dir", "speichere", "remember"))
        generate_like = any(
            k in user_bits
            for k in ("schreibe", "linkedin", "instagram", "post", "gener", "caption", "bild")
        )
        if generate_like and not store_like and not web_like and "check_post_data_completeness" in available:
            if not getattr(self, "_post_data_checked", False):
                self._post_data_checked = True
                return _call("check_post_data_completeness", {})

        should_search = (
            not self._rag_tool_used
            and ("pdf" in user_bits or "brand guidelines" in user_bits or "gedächtnis" in user_bits)
            and "memory_search" in available
        )
        if should_search:
            self._rag_tool_used = True
            return _call("memory_search", {"query": "brand guidelines pdf", "n_results": 3})

        # After completeness, if get_post_data requested in script
        if getattr(self, "force_get_post_data", False) and not getattr(self, "_post_data_read", False):
            if "get_post_data" in available:
                self._post_data_read = True
                return _call("get_post_data", {})

        return {"content": "No further tools needed.", "tool_calls": []}


    def describe_image(self, image_bytes: bytes) -> str:
        return "a marketing product photo on a clean desk"

    def generate_image(self, prompt: str, negative_prompt: str | None = None) -> bytes:
        if self.image_failures > 0:
            self.image_failures -= 1
            raise RuntimeError("HuggingFace image transient error: TimeoutError: temporary unavailable")
        return b"fake-png-bytes"

    def generate_image_from_image(
        self,
        prompt: str,
        image_bytes: bytes,
        *,
        negative_prompt: str | None = None,
        strength: float = 0.7,
    ) -> bytes:
        self.img2img_calls.append(
            {
                "prompt": prompt,
                "image_bytes": image_bytes,
                "negative_prompt": negative_prompt,
                "strength": strength,
            }
        )
        if self.image_failures > 0:
            self.image_failures -= 1
            raise RuntimeError("HuggingFace image transient error: TimeoutError: temporary unavailable")
        return b"fake-img2img-png-bytes"


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

    def list_entries(self) -> list[dict]:
        return [
            {"content": content, "content_hash": f"hash-{index}", "tags": tags}
            for index, (content, tags) in enumerate(self.stored)
        ]

    def delete(self, content_hash: str) -> bool:
        index = next(
            (i for i, _ in enumerate(self.stored) if f"hash-{i}" == content_hash),
            None,
        )
        if index is None:
            return False
        self.stored.pop(index)
        return True


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
        "text_context": None,
        "text_length": None,
        "image_context": None,
        "image_style": None,
        "preview": None,
    }
    post.update(fields)
    return graph.post_repository.save(post)


def build_agent_service(tmp_path: Path, hf: FakeHF) -> AgentService:
    from app.core import config as config_module

    config_module.settings.chats_file = tmp_path / "chats.json"
    config_module.settings.traces_file = tmp_path / "traces.json"
    config_module.settings.agent_logs_file = tmp_path / "agent_logs.json"
    config_module.settings.posts_file = tmp_path / "posts.json"
    config_module.settings.generated_images_dir = tmp_path / "generated_images"

    service = AgentService()
    service._hf = lambda: hf
    return service


def tiny_png_bytes(color: tuple[int, int, int] = (20, 40, 60)) -> bytes:
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (16, 16), color=color).save(buffer, format="PNG")
    return buffer.getvalue()
