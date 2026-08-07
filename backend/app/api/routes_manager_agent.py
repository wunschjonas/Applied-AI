from fastapi import APIRouter

from app.schemas.chat import (
    ChatHistoryResponse,
    ManagerChatRequest,
    ManagerChatResponse,
    ManagerGenerateRequest,
)
from app.schemas.logs import AgentLogsResponse
from app.services.agent_service import AgentService
from app.services.chat_service import ChatService
from app.services.log_service import LogService

router = APIRouter(prefix="/api/agents/manager", tags=["manager-agent"])

agent_service = AgentService()
chat_service = ChatService()
log_service = LogService()


@router.post("/chat", response_model=ManagerChatResponse)
def manager_chat(request: ManagerChatRequest):
    print(f"[ManagerAgent] POST /chat aufgerufen | post_id={request.post_id} | message='{request.message[:80]}'")
    return agent_service.manager_chat(
        message=request.message,
        post_id=request.post_id,
        context=request.context,
    )


@router.post("/generate", response_model=ManagerChatResponse)
def manager_generate(request: ManagerGenerateRequest):
    print(f"[ManagerAgent] POST /generate aufgerufen | post_id={request.post_id}")
    return agent_service.manager_generate(post_id=request.post_id)


@router.get("/chats/{chat_id}", response_model=ChatHistoryResponse)
def get_chat(chat_id: str):
    print(f"[ManagerAgent] GET /chats/{chat_id} aufgerufen")
    return chat_service.get_chat(chat_id)


@router.get("/logs", response_model=AgentLogsResponse)
def get_logs():
    print("[ManagerAgent] GET /logs aufgerufen")
    logs = log_service.get_logs_by_agent("manager_agent")
    return AgentLogsResponse(agent="manager_agent", total=len(logs), logs=logs)
