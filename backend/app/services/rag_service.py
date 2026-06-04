from __future__ import annotations

from typing import Any


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

    def is_needed(self, message: str) -> bool:
        normalized = message.lower()
        return any(keyword in normalized for keyword in self.rag_keywords)

    def retrieve(self, message: str, context: str | dict[str, Any] | None = None) -> str:
        return "RAG requested, but retrieval is not implemented yet in this version."
