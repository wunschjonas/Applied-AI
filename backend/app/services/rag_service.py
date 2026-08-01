from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import re
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from mcp import ClientSession

try:
    from mcp.client.streamable_http import streamable_http_client as streamablehttp_client
except ImportError:  # older mcp package name
    from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)

MEMORY_SEARCH_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "memory_search",
        "description": (
            "Search stored brand facts, uploaded documents/images, and project memory. "
            "Call this when the user asks what is in memory/RAG/Gedaechtnis, or when stored "
            "facts may help write or illustrate the marketing post."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Short search query focused on brand facts, docs, images, or constraints.",
                },
                "n_results": {
                    "type": "integer",
                    "description": "Maximum number of memory hits to return.",
                    "default": 3,
                },
            },
            "required": ["query"],
        },
    },
}


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(0, end - overlap)
    return chunks


def _run_coro(coro: Any) -> Any:
    """Run an async MCP call from sync FastAPI/thread contexts safely."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # Already inside an event loop: run in a fresh loop on a worker thread.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result(timeout=60)


class RAGService:
    rag_keywords = {
        "uploaded document",
        "pdf",
        "brand guidelines",
        "knowledge base",
        "unsere daten",
        "dokument",
        "quelle",
        "gedächtnis",
        "gedachtnis",
        "gedaechtnis",
        "memory",
        "rag",
        "context",
    }

    def __init__(self, memory_url: str = "http://localhost:8765/mcp"):
        self.memory_url = memory_url

    def is_needed(self, message: str) -> bool:
        normalized = message.lower()
        return any(keyword in normalized for keyword in self.rag_keywords)

    def search(self, query: str, n_results: int = 3) -> str:
        try:
            return _run_coro(self._search(query, n_results=n_results))
        except Exception as exc:
            logger.warning("Memory search failed: %s", exc)
            return ""

    def retrieve(self, query: str, context: str | dict[str, Any] | None = None) -> str:
        return self.search(query, n_results=3)

    def store(self, content: str, tags: list[str] | None = None) -> None:
        try:
            _run_coro(self._store(content, tags or []))
        except Exception as exc:
            logger.warning("Memory store failed: %s", exc)
            raise

    def list_all(self) -> list[str]:
        try:
            return _run_coro(self._list())
        except Exception as exc:
            logger.warning("Memory list failed: %s", exc)
            return []

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[ClientSession]:
        """Open an MCP streamable-http session (SDK yields 2- or 3-tuples)."""
        async with streamablehttp_client(self.memory_url) as transport:
            if len(transport) == 2:
                read, write = transport
            else:
                read, write, _get_session_id = transport
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    async def _search(self, query: str, n_results: int = 3) -> str:
        async with self._session() as session:
            result = await session.call_tool(
                "memory_search", {"query": query, "n_results": n_results}
            )
        contents = self._extract_contents(result)
        return "\n".join(contents) if contents else ""

    async def _store(self, content: str, tags: list[str]) -> None:
        async with self._session() as session:
            await session.call_tool(
                "memory_store", {"content": content, "tags": tags}
            )

    async def _list(self) -> list[str]:
        async with self._session() as session:
            result = await session.call_tool("memory_list", {})
        return self._extract_contents(result)

    def _extract_contents(self, result: Any) -> list[str]:
        """Parse MCP tool result — Memory Service returns JSON with memories/results/entries."""
        raw_texts = [item.text for item in result.content if hasattr(item, "text") and item.text]
        contents: list[str] = []
        for text in raw_texts:
            parsed = self._parse_memory_payload(text)
            if parsed:
                contents.extend(parsed)
            else:
                contents.append(text)
        return contents

    def _parse_memory_payload(self, text: str) -> list[str]:
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return self._parse_plain_memory_text(text)

        if isinstance(data, list):
            return [str(item.get("content") or item.get("text") or item) for item in data if item]

        if not isinstance(data, dict):
            return [str(data)]

        for key in ("memories", "results", "entries", "items", "data"):
            values = data.get(key)
            if isinstance(values, list):
                out: list[str] = []
                for mem in values:
                    if isinstance(mem, dict):
                        content = mem.get("content") or mem.get("text") or mem.get("memory")
                        if content:
                            out.append(str(content))
                    elif mem:
                        out.append(str(mem))
                return out

        content = data.get("content") or data.get("text")
        return [str(content)] if content else []

    def _parse_plain_memory_text(self, text: str) -> list[str]:
        """Parse human-readable MCP memory_search output into content lines."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        contents: list[str] = []
        for line in lines:
            match = re.match(r"^\d+\.\s+(.+)$", line)
            if match:
                contents.append(match.group(1).strip())
        return contents
