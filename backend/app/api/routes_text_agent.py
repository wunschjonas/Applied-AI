from fastapi import APIRouter

from app.schemas.agent import TextGenerateRequest, TextGenerateResponse
from app.schemas.logs import AgentLogsResponse
from app.services.agent_service import AgentService
from app.services.log_service import LogService

router = APIRouter(prefix="/api/agents/text", tags=["text-agent"])

agent_service = AgentService()
log_service = LogService()


@router.post("/generate", response_model=TextGenerateResponse)
def generate_text(request: TextGenerateRequest):
    print("[TextAgent] POST /generate aufgerufen")
    return agent_service.generate_text(
        task=request.task,
        platform=request.platform,
        tone=request.tone,
        target_audience=request.target_audience,
        context=request.context,
    )


@router.get("/logs", response_model=AgentLogsResponse)
def get_logs():
    print("[TextAgent] GET /logs aufgerufen")
    logs = log_service.get_logs_by_agent("text_agent")
    return AgentLogsResponse(agent="text_agent", total=len(logs), logs=logs)
