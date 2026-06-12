from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from app.core.config import settings
from app.schemas.post import PostCreate, PostInit, PostInitResponse, PostResponse, PostStatus, PostUpdate
from app.services.agent_service import AgentService
from app.storage.json_store import JSONStore


class PostService:
    def __init__(self):
        self.store = JSONStore(settings.posts_file)

    def init_post(self, post_init: PostInit) -> PostInitResponse:
        post_id = str(uuid4())
        post = {
            "id": post_id,
            "title": post_init.title,
            "status": PostStatus.draft.value,
            "topic": None,
            "platform": None,
            "target_audience": None,
            "tone_of_voice": None,
            "additional_context": None,
            "preview": None,
        }
        self.store.save(post)
        return PostInitResponse(post_id=post_id, title=post_init.title)

    def create_post(self, post_create: PostCreate) -> PostResponse:
        post = {
            "id": str(uuid4()),
            "status": PostStatus.draft.value,
            "preview": None,
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
        post.update(post_update.model_dump(exclude_none=True))
        self.store.save(post)
        return self._to_response(post)

    def delete_post(self, post_id: str) -> None:
        if not self.store.delete(post_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    def generate_preview(self, post_id: str) -> PostResponse:
        post = self.store.get(post_id)
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

        post["status"] = PostStatus.processing.value
        self.store.save(post)

        try:
            parts = [
                f"Create a {post['platform']} post about {post['topic']}",
                f"for {post['target_audience']}" if post.get("target_audience") else "",
                f"in a {post['tone_of_voice']} tone." if post.get("tone_of_voice") else ".",
                post.get("additional_context") or "",
            ]
            message = " ".join(p for p in parts if p).strip()

            result = AgentService().manager_chat(
                message=message,
                post_id=post_id,
                context={
                    "tone": post.get("tone_of_voice"),
                    "target_audience": post.get("target_audience"),
                },
            )
            text_artifact = result["generated_artifacts"].get("text", {})
            image_artifact = result["generated_artifacts"].get("image", {})

            post["preview"] = {
                "generated_text": text_artifact.get("generated_text", result["assistant_message"]),
                "post_structure": {
                    "manager_response": result["assistant_message"],
                    "used_agents": result["used_agents"],
                },
                "hashtags": text_artifact.get("hashtags", []),
                "image_prompt_optional": image_artifact.get("image_prompt"),
            }
            post["status"] = PostStatus.preview_ready.value
            self.store.save(post)
            return self._to_response(post)

        except Exception as exc:
            post["status"] = PostStatus.error.value
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

    def _to_response(self, post: dict[str, Any]) -> PostResponse:
        allowed = {"id", "title", "status", "topic", "platform", "target_audience", "tone_of_voice", "additional_context", "preview"}
        return PostResponse(**{k: v for k, v in post.items() if k in allowed})
