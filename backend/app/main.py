import logging

from fastapi import FastAPI, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes_image_agent import router as image_router
from app.api.routes_logs import router as logs_router
from app.api.routes_manager_agent import router as manager_router
from app.api.routes_memory import router as memory_router
from app.api.routes_posts import router as posts_router
from app.api.routes_text_agent import router as text_router
from app.core.config import settings
from app.services.health_service import build_health_report
import app.metrics  # noqa: F401 — register custom counters on default registry

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Applied AI Marketing Agent Backend",
    version=settings.app_version,
    description="FastAPI backend for marketing agent chat, delegation, traces and post previews.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(posts_router)
app.include_router(manager_router)
app.include_router(text_router)
app.include_router(image_router)
app.include_router(memory_router)
app.include_router(logs_router)

settings.generated_images_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    "/generated-images",
    StaticFiles(directory=settings.generated_images_dir),
    name="generated-images",
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Keep FastAPI defaults for HTTP / validation errors; only sanitize true crashes.
    if isinstance(exc, StarletteHTTPException):
        return await http_exception_handler(request, exc)
    if isinstance(exc, RequestValidationError):
        return await request_validation_exception_handler(request, exc)
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
def health():
    return build_health_report()
