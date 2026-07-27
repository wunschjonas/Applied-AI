from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_image_agent import router as image_router
from app.api.routes_manager_agent import router as manager_router
from app.api.routes_memory import router as memory_router
from app.api.routes_posts import router as posts_router
from app.api.routes_text_agent import router as text_router
from app.core.config import settings

app = FastAPI(
    title="Applied AI Marketing Agent Backend",
    version=settings.app_version,
    description="FastAPI backend for marketing agent chat, delegation, traces and post previews.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(posts_router)
app.include_router(manager_router)
app.include_router(text_router)
app.include_router(image_router)
app.include_router(memory_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "applied-ai-marketing-agent",
        "version": settings.app_version,
    }
