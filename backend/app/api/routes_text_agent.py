from fastapi import APIRouter

from app.schemas.agent import TextGenerateRequest, TextGenerateResponse
from app.services.agent_service import AgentService

router = APIRouter(prefix="/api/agents/text", tags=["text-agent"])

agent_service = AgentService()


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


@router.get("/logs")
def get_logs():
    print("[TextAgent] GET /logs aufgerufen")
    pass
