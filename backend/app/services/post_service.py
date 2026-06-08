from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from app.core.config import settings
from app.schemas.post import PostCreate, PostResponse, PostStatus, PostUpdate
from app.services.agent_service import AgentService
from app.services.trace_service import TraceService
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
            message = (
                f"Create a {post['platform']} post about {post['topic']} for "
                f"{post['target_audience']} in a {post['tone_of_voice']} tone. Goal: {post['goal']}. "
                f"{post.get('additional_context') or ''}"
            )
            result = AgentService().manager_chat(
                message=message,
                context={
                    "tone": post["tone_of_voice"],
                    "target_audience": post["target_audience"],
                },
            )
            text_artifact = result["generated_artifacts"].get("text", {})
            image_artifact = result["generated_artifacts"].get("image", {})
            trace = TraceService().get_trace(result["trace_id"])

            post["preview"] = {
                "generated_text": text_artifact.get("generated_text", result["assistant_message"]),
                "post_structure": {
                    "manager_response": result["assistant_message"],
                    "used_agents": result["used_agents"],
                },
                "hashtags": text_artifact.get("hashtags", []),
                "image_prompt_optional": image_artifact.get("image_prompt"),
                "created_at": datetime.utcnow().isoformat(),
            }
            post["agent_trace"] = [
                {
                    "timestamp": step["timestamp"],
                    "thought": step["decision"],
                    "action": step["action"],
                    "observation": step["observation"],
                }
                for step in trace["steps"]
            ]
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
