from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from app.core.config import settings
from app.graphs.support import post_data_llm
from app.graphs.support.post_fields import AWAITING_FIELD_KEY, missing_fields
from app.schemas.post import Platform, PostCreate, PostInit, PostInitResponse, PostResponse, PostStatus, PostUpdate
from app.services.agent_service import AgentService
from app.services.chat_service import ChatService
from app.services.huggingface_service import HuggingFaceService
from app.services.post_repository import PostRepository


class PostService:
    def __init__(self):
        self.store = PostRepository()
        self.chat_service = ChatService()

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
            "text_context": None,
            "text_length": None,
            "image_context": None,
            "image_style": None,
            "preview": None,
            AWAITING_FIELD_KEY: "topic",
        }
        self.store.save(post)
        self.chat_service.ensure_chats_for_post(post_id)

        welcome = post_data_llm.welcome_message(post_init.title, self._optional_hf())
        chat = self.chat_service.get_or_create_chat(post_id, agent="manager_agent")
        self.chat_service.add_message(chat, "AGENT", welcome)

        return PostInitResponse(
            post_id=post_id,
            title=post_init.title,
            welcome_message=welcome,
            missing_fields=missing_fields(post),
        )

    def _optional_hf(self) -> HuggingFaceService | None:
        token = settings.hf_token.get_secret_value() if settings.hf_token else None
        if not token:
            return None
        try:
            return HuggingFaceService(
                hf_token=token,
                hf_model_id=settings.hf_model_id,
                hf_image_model_id=settings.hf_image_model_id,
                hf_caption_model_id=settings.hf_caption_model_id,
                hf_image_to_image_model_id=settings.hf_image_to_image_model_id,
                timeout=settings.hf_timeout_seconds,
                image_timeout=settings.hf_image_timeout_seconds,
            )
        except Exception:
            return None

    def create_post(self, post_create: PostCreate) -> PostResponse:
        post = {
            "id": str(uuid4()),
            "status": PostStatus.draft.value,
            "preview": None,
            **post_create.model_dump(),
        }
        self.store.save(post)
        self.chat_service.ensure_chats_for_post(post["id"])
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
        self.chat_service.delete_chats_for_post(post_id)

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
                f"Text focus: {post['text_context']}." if post.get("text_context") else "",
                f"Text length: {post['text_length']}." if post.get("text_length") else "",
                f"Image motif: {post['image_context']}." if post.get("image_context") else "",
                f"Image style: {post['image_style']}." if post.get("image_style") else "",
            ]
            message = " ".join(p for p in parts if p).strip()

            result = AgentService().manager_chat(
                message=message,
                post_id=post_id,
                context={
                    "tone": post.get("tone_of_voice"),
                    "target_audience": post.get("target_audience"),
                    "text_context": post.get("text_context"),
                    "text_length": post.get("text_length"),
                    "image_context": post.get("image_context"),
                    "image_style": post.get("image_style"),
                },
            )

            # The graph writes artifacts into post.preview itself; only reload here.
            post = self.store.get(post_id) or post
            if not post.get("preview"):
                post["preview"] = {
                    "generated_text": result["assistant_message"],
                    "post_structure": {
                        "manager_response": result["assistant_message"],
                        "used_agents": result["used_agents"],
                    },
                    "hashtags": [],
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
        allowed = {
            "id",
            "title",
            "status",
            "topic",
            "platform",
            "target_audience",
            "tone_of_voice",
            "text_context",
            "text_length",
            "image_context",
            "image_style",
            "preview",
        }
        payload = {k: v for k, v in post.items() if k in allowed}
        platform = payload.get("platform")
        if platform is not None:
            try:
                Platform(platform)
            except ValueError:
                # Corrupt brief values must not break the whole posts API.
                payload["platform"] = None
        payload["missing_fields"] = missing_fields(post)
        return PostResponse(**payload)
