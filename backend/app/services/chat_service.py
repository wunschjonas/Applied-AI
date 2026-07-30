from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.core.config import settings
from app.storage.json_store import JSONStore


class ChatService:
    AGENT_CHAT_TYPES = ("manager_agent", "text_agent", "image_agent")

    def __init__(self):
        self.store = JSONStore(settings.chats_file)

    def get_or_create_chat(self, post_id: str, agent: str) -> dict[str, Any]:
        chat_id = f"{post_id}::{agent}"
        chat = self.store.get(chat_id)
        if chat:
            return chat

        chat = {
            "id": chat_id,
            "agent": agent,
            "messages": [],
        }
        self.store.save(chat)
        return chat

    def ensure_chats_for_post(self, post_id: str) -> None:
        for agent in self.AGENT_CHAT_TYPES:
            self.get_or_create_chat(post_id, agent)

    def delete_chats_for_post(self, post_id: str) -> None:
        prefix = f"{post_id}::"
        for chat in list(self.store.list()):
            chat_id = chat.get("id", "")
            if isinstance(chat_id, str) and chat_id.startswith(prefix):
                self.store.delete(chat_id)

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
        }
        if metadata:
            message["metadata"] = metadata
        chat["messages"].append(message)
        self.store.save(chat)
        return message

    def get_chat(self, chat_id: str) -> dict[str, Any]:
        chat = self.store.get(chat_id)
        if not chat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        return chat

    def get_chats_by_agent(self, agent: str) -> list[dict[str, Any]]:
        return [c for c in self.store.list() if c.get("agent") == agent]
