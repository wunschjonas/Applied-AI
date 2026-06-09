from fastapi import APIRouter

from app.schemas.agent import ImagePromptRequest, ImagePromptResponse
from app.schemas.logs import AgentLogsResponse
from app.services.agent_service import AgentService
from app.services.log_service import LogService

router = APIRouter(prefix="/api/agents/image", tags=["image-agent"])

agent_service = AgentService()
log_service = LogService()


@router.post("/generate-prompt", response_model=ImagePromptResponse)
def generate_image_prompt(request: ImagePromptRequest):
    print("[ImageAgent] POST /generate-prompt aufgerufen")
    return agent_service.generate_image_prompt(
        task=request.task,
        platform=request.platform,
        visual_style=request.visual_style,
        context=request.context,
    )


@router.get("/logs", response_model=AgentLogsResponse)
def get_logs():
    print("[ImageAgent] GET /logs aufgerufen")
    logs = log_service.get_logs_by_agent("image_agent")
    return AgentLogsResponse(agent="image_agent", total=len(logs), logs=logs)
