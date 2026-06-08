from fastapi import APIRouter

from app.schemas.chat import ChatHistoryResponse, ManagerChatRequest, ManagerChatResponse
from app.schemas.trace import TraceResponse
from app.services.agent_service import AgentService
from app.services.chat_service import ChatService
from app.services.trace_service import TraceService

router = APIRouter(prefix="/api/agents/manager", tags=["manager-agent"])

agent_service = AgentService()
chat_service = ChatService()
trace_service = TraceService()


@router.post("/chat", response_model=ManagerChatResponse)
def manager_chat(request: ManagerChatRequest):
    print("[ManagerAgent] POST /chat aufgerufen")
    return agent_service.manager_chat(
        message=request.message,
        chat_id=request.chat_id,
        context=request.context,
    )


@router.get("/chats/{chat_id}", response_model=ChatHistoryResponse)
def get_chat(chat_id: str):
    print(f"[ManagerAgent] GET /chats/{chat_id} aufgerufen")
    return chat_service.get_chat(chat_id)


@router.get("/traces/{trace_id}", response_model=TraceResponse)
def get_trace(trace_id: str):
    print(f"[ManagerAgent] GET /traces/{trace_id} aufgerufen")
    return trace_service.get_trace(trace_id)


@router.get("/logs")
def get_logs():
    print("[ManagerAgent] GET /logs aufgerufen")
    pass
