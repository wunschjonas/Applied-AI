from fastapi import APIRouter

from app.schemas.agent import ImagePromptRequest, ImagePromptResponse
from app.services.agent_service import AgentService

router = APIRouter(prefix="/api/agents/image", tags=["image-agent"])

agent_service = AgentService()


@router.post("/generate-prompt", response_model=ImagePromptResponse)
def generate_image_prompt(request: ImagePromptRequest):
    print("[ImageAgent] POST /generate-prompt aufgerufen")
    return agent_service.generate_image_prompt(
        task=request.task,
        platform=request.platform,
        visual_style=request.visual_style,
        context=request.context,
    )


@router.get("/logs")
def get_logs():
    print("[ImageAgent] GET /logs aufgerufen")
    pass
