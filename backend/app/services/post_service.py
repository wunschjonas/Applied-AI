from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from app.agents.manager_agent import ManagerAgent
from app.core.config import settings
from app.schemas.post import PostCreate, PostResponse, PostStatus, PostUpdate
from app.storage.json_store import JSONStore


class PostService:
    def __init__(self):
        self.store = JSONStore(settings.posts_file)

    def create_post(self, post_create: PostCreate) -> PostResponse:
        now = datetime.utcnow().isoformat()

        post = {
            "id": str(uuid4()),
            "status": PostStatus.draft.value,
            "preview": None,
            "agent_trace": [],
            "created_at": now,
            "updated_at": now,
            **post_create.model_dump(),
        }

        self.store.save(post)
        return self._to_response(post)

    def list_posts(self) -> list[PostResponse]:
        return [self._to_response(post) for post in self.store.list()]

    def get_post(self, post_id: str) -> PostResponse:
        post = self.store.get(post_id)

        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

        return self._to_response(post)

    def update_post(self, post_id: str, post_update: PostUpdate) -> PostResponse:
        post = self.store.get(post_id)

        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

        updates = post_update.model_dump(exclude_none=True)

        post.update(updates)
        post["updated_at"] = datetime.utcnow().isoformat()

        self.store.save(post)
        return self._to_response(post)

    def delete_post(self, post_id: str) -> None:
        deleted = self.store.delete(post_id)

        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    def generate_preview(self, post_id: str) -> PostResponse:
        post = self.store.get(post_id)

        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

        post["status"] = PostStatus.processing.value
        post["updated_at"] = datetime.utcnow().isoformat()
        self.store.save(post)

        try:
            hf_token = settings.hf_token.get_secret_value() if settings.hf_token else None

            agent = ManagerAgent(
                hf_token=hf_token,
                hf_model_id=settings.hf_model_id,
            )

            result = agent.run(post)

            post["preview"] = result["preview"]
            post["agent_trace"] = result["agent_trace"]
            post["status"] = PostStatus.preview_ready.value
            post["updated_at"] = datetime.utcnow().isoformat()

            self.store.save(post)
            return self._to_response(post)

        except Exception as exc:
            post["status"] = PostStatus.error.value
            post["updated_at"] = datetime.utcnow().isoformat()
            self.store.save(post)

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Preview generation failed: {type(exc).__name__}: {str(exc)}",
            )

    def get_preview(self, post_id: str) -> dict[str, Any]:
        post = self.store.get(post_id)

        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

        if not post.get("preview"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preview not found")

        return post["preview"]

    def get_agent_trace(self, post_id: str) -> list[dict[str, Any]]:
        post = self.store.get(post_id)

        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

        return post.get("agent_trace", [])

    def _to_response(self, post: dict[str, Any]) -> PostResponse:
        return PostResponse(**post)