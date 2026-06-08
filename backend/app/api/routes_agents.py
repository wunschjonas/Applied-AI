from fastapi import APIRouter

from app.schemas.agent import (
    ImagePromptRequest,
    ImagePromptResponse,
    TextGenerateRequest,
    TextGenerateResponse,
)
from app.schemas.chat import ChatHistoryResponse, ManagerChatRequest, ManagerChatResponse
from app.schemas.trace import TraceResponse
from app.services.agent_service import AgentService
from app.services.chat_service import ChatService
from app.services.trace_service import TraceService

router = APIRouter(prefix="/api/agents", tags=["agents"])

agent_service = AgentService()
chat_service = ChatService()
trace_service = TraceService()


@router.post("/manager/chat", response_model=ManagerChatResponse)
def manager_chat(request: ManagerChatRequest):
    return agent_service.manager_chat(
        message=request.message,
        chat_id=request.chat_id,
        context=request.context,
    )


@router.get("/chats/{chat_id}", response_model=ChatHistoryResponse)
def get_chat(chat_id: str):
    return chat_service.get_chat(chat_id)


@router.get("/traces/{trace_id}", response_model=TraceResponse)
def get_trace(trace_id: str):
    return trace_service.get_trace(trace_id)


@router.post("/text/generate", response_model=TextGenerateResponse)
def generate_text(request: TextGenerateRequest):
    return agent_service.generate_text(
        task=request.task,
        platform=request.platform,
        tone=request.tone,
        target_audience=request.target_audience,
        context=request.context,
    )


@router.post("/image/generate-prompt", response_model=ImagePromptResponse)
def generate_image_prompt(request: ImagePromptRequest):
    return agent_service.generate_image_prompt(
        task=request.task,
        platform=request.platform,
        visual_style=request.visual_style,
        context=request.context,
    )
