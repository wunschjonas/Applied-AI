from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from app.core.config import settings
from app.storage.json_store import JSONStore


class ChatService:
    def __init__(self):
        self.store = JSONStore(settings.chats_file)

    def get_or_create_chat(self, chat_id: str | None = None, agent: str = "manager_agent") -> dict[str, Any]:
        if chat_id:
            chat = self.store.get(chat_id)
            if not chat:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
            return chat

        now = datetime.utcnow().isoformat()
        chat_id = str(uuid4())
        chat = {
            "id": chat_id,
            "chat_id": chat_id,
            "agent": agent,
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
        self.store.save(chat)
        return chat

    def add_message(
        self,
        chat: dict[str, Any],
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        chat["messages"].append(message)
        chat["updated_at"] = datetime.utcnow().isoformat()
        self.store.save(chat)
        return message

    def get_chat(self, chat_id: str) -> dict[str, Any]:
        chat = self.store.get(chat_id)

        if not chat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

        return chat

    def get_chats_by_agent(self, agent: str) -> list[dict[str, Any]]:
        return [c for c in self.store.list() if c.get("agent") == agent]
