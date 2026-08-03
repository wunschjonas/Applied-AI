from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.schemas.agent import ImageGenerateResponse, ImagePromptRequest, ImagePromptResponse
from app.schemas.chat import ChatHistoryResponse, ImageAgentChatResponse
from app.schemas.logs import AgentLogsResponse
from app.services.agent_service import AgentService
from app.services.chat_service import ChatService
from app.services.log_service import LogService

router = APIRouter(prefix="/api/agents/image", tags=["image-agent"])

agent_service = AgentService()
chat_service = ChatService()
log_service = LogService()

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/jpg"}
ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MAX_SOURCE_IMAGE_BYTES = 8 * 1024 * 1024


def _is_allowed_source_image(filename: str | None, content_type: str | None, data: bytes) -> bool:
    mime = (content_type or "").lower().split(";", 1)[0].strip()
    suffix = Path(filename or "").suffix.lower()
    if mime in ALLOWED_IMAGE_TYPES or suffix in ALLOWED_IMAGE_SUFFIXES:
        return True
    if data.startswith(b"\x89PNG\r\n\x1a\n") or data[:3] == b"\xff\xd8\xff":
        return True
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return True
    return False


@router.post("/generate-prompt", response_model=ImagePromptResponse)
def generate_image_prompt(request: ImagePromptRequest):
    print("[ImageAgent] POST /generate-prompt aufgerufen")
    return agent_service.generate_image_prompt(
        task=request.task,
        platform=request.platform,
        visual_style=request.visual_style,
        context=request.context,
    )


@router.post("/generate", response_model=ImageGenerateResponse)
def generate_image(request: ImagePromptRequest):
    print(f"[ImageAgent] POST /generate aufgerufen | post_id={request.post_id}")
    return agent_service.generate_image(
        task=request.task,
        platform=request.platform,
        visual_style=request.visual_style,
        context=request.context,
        post_id=request.post_id,
    )


@router.post("/chat", response_model=ImageAgentChatResponse)
async def image_agent_chat(
    message: str = Form(..., min_length=1, max_length=4000),
    post_id: str = Form(...),
    strength: float = Form(0.7),
    source_image: UploadFile | None = File(None),
):
    source_bytes: bytes | None = None
    if source_image is not None and (source_image.filename or source_image.content_type):
        source_bytes = await source_image.read()
        if not source_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="source_image is empty.",
            )
        if len(source_bytes) > MAX_SOURCE_IMAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="source_image exceeds the 8 MB limit.",
            )
        if not _is_allowed_source_image(source_image.filename, source_image.content_type, source_bytes):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="source_image must be PNG, JPEG, or WebP.",
            )

    print(
        f"[ImageAgent] POST /chat aufgerufen | post_id={post_id} | "
        f"message='{message[:80]}' | has_source_image={bool(source_bytes)}"
    )
    return agent_service.image_agent_chat(
        message=message,
        post_id=post_id,
        source_image=source_bytes,
        strength=strength,
    )


@router.get("/chats/{chat_id}", response_model=ChatHistoryResponse)
def get_chat(chat_id: str):
    print(f"[ImageAgent] GET /chats/{chat_id} aufgerufen")
    return chat_service.get_chat(chat_id)


@router.get("/logs", response_model=AgentLogsResponse)
def get_logs():
    print("[ImageAgent] GET /logs aufgerufen")
    logs = log_service.get_logs_by_agent("image_agent")
    return AgentLogsResponse(agent="image_agent", total=len(logs), logs=logs)
