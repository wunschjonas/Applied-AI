from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)


class RAGService:
    rag_keywords = {
        "uploaded document",
        "pdf",
        "brand guidelines",
        "knowledge base",
        "unsere daten",
        "dokument",
        "quelle",
        "context",
    }

    def __init__(self, memory_url: str = "http://localhost:8765/mcp"):
        self.memory_url = memory_url

    def is_needed(self, message: str) -> bool:
        normalized = message.lower()
        return any(keyword in normalized for keyword in self.rag_keywords)

    def retrieve(self, query: str, context: str | dict[str, Any] | None = None) -> str:
        try:
            return asyncio.run(self._search(query))
        except Exception as exc:
            logger.warning("Memory search failed: %s", exc)
            return ""

    def store(self, content: str, tags: list[str] | None = None) -> None:
        try:
            asyncio.run(self._store(content, tags or []))
        except Exception as exc:
            logger.warning("Memory store failed: %s", exc)

    def list_all(self) -> list[str]:
        try:
            return asyncio.run(self._list())
        except Exception as exc:
            logger.warning("Memory list failed: %s", exc)
            return []

    async def _search(self, query: str) -> str:
        async with streamablehttp_client(self.memory_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "memory_search", {"query": query, "n_results": 3}
                )
        contents = self._extract_contents(result)
        return "\n".join(contents) if contents else ""

    async def _store(self, content: str, tags: list[str]) -> None:
        async with streamablehttp_client(self.memory_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                await session.call_tool(
                    "memory_store", {"content": content, "tags": tags}
                )

    async def _list(self) -> list[str]:
        async with streamablehttp_client(self.memory_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("memory_list", {})
        return self._extract_contents(result)

    def _extract_contents(self, result: Any) -> list[str]:
        """Parse MCP tool result — the Memory Service returns a JSON object with a 'memories' array."""
        raw_texts = [item.text for item in result.content if hasattr(item, "text") and item.text]
        contents: list[str] = []
        for text in raw_texts:
            try:
                data = json.loads(text)
                memories = data.get("memories", [])
                for mem in memories:
                    content = mem.get("content") or mem.get("text") or str(mem)
                    if content:
                        contents.append(content)
            except (json.JSONDecodeError, AttributeError):
                contents.append(text)
        return contents
