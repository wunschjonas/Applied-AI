from fastapi import APIRouter

from app.schemas.chat import ChatHistoryResponse, TextAgentChatRequest, TextAgentChatResponse
from app.schemas.logs import AgentLogsResponse
from app.services.agent_service import AgentService
from app.services.chat_service import ChatService
from app.services.log_service import LogService

router = APIRouter(prefix="/api/agents/text", tags=["text-agent"])

agent_service = AgentService()
chat_service = ChatService()
log_service = LogService()


@router.post("/chat", response_model=TextAgentChatResponse)
def text_agent_chat(request: TextAgentChatRequest):
    print(f"[TextAgent] POST /chat aufgerufen | post_id={request.post_id} | message='{request.message[:80]}'")
    return agent_service.text_agent_chat(message=request.message, post_id=request.post_id)


@router.get("/chats/{chat_id}", response_model=ChatHistoryResponse)
def get_chat(chat_id: str):
    print(f"[TextAgent] GET /chats/{chat_id} aufgerufen")
    return chat_service.get_chat(chat_id)


@router.get("/logs", response_model=AgentLogsResponse)
def get_logs():
    print("[TextAgent] GET /logs aufgerufen")
    logs = log_service.get_logs_by_agent("text_agent")
    return AgentLogsResponse(agent="text_agent", total=len(logs), logs=logs)
