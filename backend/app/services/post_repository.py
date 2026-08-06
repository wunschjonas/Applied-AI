from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.storage.json_store import JSONStore


class PostRepository:
    """Direct post storage access.

    Kept free of agent imports so the LangGraph nodes can read and write posts
    without pulling in PostService, which depends on AgentService.
    """

    def __init__(self):
        self.store = JSONStore(settings.posts_file)

    def get(self, post_id: str) -> dict[str, Any] | None:
        return self.store.get(post_id)

    def save(self, post: dict[str, Any]) -> dict[str, Any]:
        return self.store.save(post)

    def list(self) -> list[dict[str, Any]]:
        return self.store.list()

    def delete(self, post_id: str) -> bool:
        return self.store.delete(post_id)

    def update_fields(self, post_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        if not fields:
            return self.get(post_id)

        post = self.get(post_id)
        if not post:
            return None

        post.update(fields)
        return self.save(post)

    def merge_preview(self, post_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        """Merge artifact fields into post.preview so a text-only run keeps an earlier image."""
        if not patch:
            return self.get(post_id)

        post = self.get(post_id)
        if not post:
            return None

        preview = dict(post.get("preview") or {})
        preview.update(patch)
        post["preview"] = preview
        return self.save(post)
