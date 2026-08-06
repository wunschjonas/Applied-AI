from __future__ import annotations

from fastapi import APIRouter

from app.schemas.chat import ChatHistoryResponse, ImageAgentChatRequest, ImageAgentChatResponse
from app.schemas.logs import AgentLogsResponse
from app.services.agent_service import AgentService
from app.services.chat_service import ChatService
from app.services.log_service import LogService

router = APIRouter(prefix="/api/agents/image", tags=["image-agent"])

agent_service = AgentService()
chat_service = ChatService()
log_service = LogService()


@router.post("/chat", response_model=ImageAgentChatResponse)
def image_agent_chat(request: ImageAgentChatRequest):
    print(
        f"[ImageAgent] POST /chat aufgerufen | post_id={request.post_id} | "
        f"message='{request.message[:80]}'"
    )
    return agent_service.image_agent_chat(message=request.message, post_id=request.post_id)


@router.get("/chats/{chat_id}", response_model=ChatHistoryResponse)
def get_chat(chat_id: str):
    print(f"[ImageAgent] GET /chats/{chat_id} aufgerufen")
    return chat_service.get_chat(chat_id)


@router.get("/logs", response_model=AgentLogsResponse)
def get_logs():
    print("[ImageAgent] GET /logs aufgerufen")
    logs = log_service.get_logs_by_agent("image_agent")
    return AgentLogsResponse(agent="image_agent", total=len(logs), logs=logs)
