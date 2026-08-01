from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.core.config import settings
from app.services.huggingface_service import HuggingFaceService
from app.services.rag_service import RAGService, chunk_text

router = APIRouter(prefix="/api/memory", tags=["memory"])

rag_service = RAGService(memory_url=settings.mcp_memory_url)

ALLOWED_PDF = {"application/pdf"}
ALLOWED_IMAGES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024


class MemoryStoreRequest(BaseModel):
    content: str
    tags: list[str] = []


class MemoryStoreResponse(BaseModel):
    status: str


class MemorySearchResponse(BaseModel):
    query: str
    results: list[str]


class MemoryListResponse(BaseModel):
    entries: list[str]


class MemoryUploadResponse(BaseModel):
    stored_chunks: int
    filename: str
    kind: str
    preview: str


@router.post("/store", response_model=MemoryStoreResponse, status_code=status.HTTP_201_CREATED)
def store_memory(body: MemoryStoreRequest):
    print(f"[Memory] POST /api/memory/store | content='{body.content[:60]}...'")
    try:
        rag_service.store(body.content, body.tags)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return MemoryStoreResponse(status="stored")


@router.get("/search", response_model=MemorySearchResponse)
def search_memory(q: str):
    print(f"[Memory] GET /api/memory/search | q='{q}'")
    raw = rag_service.retrieve(q)
    results = [line for line in raw.splitlines() if line.strip()] if raw else []
    return MemorySearchResponse(query=q, results=results)


@router.get("/list", response_model=MemoryListResponse)
def list_memory():
    print("[Memory] GET /api/memory/list")
    entries = rag_service.list_all()
    return MemoryListResponse(entries=entries)


@router.post("/upload", response_model=MemoryUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_memory(file: UploadFile = File(...)):
    filename = Path(file.filename or "upload.bin").name
    content_type = (file.content_type or "").lower()
    print(f"[Memory] POST /api/memory/upload | filename='{filename}' type='{content_type}'")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large (max 15MB).")

    kind = _detect_kind(filename, content_type)
    if kind == "pdf":
        text = _extract_pdf_text(data)
        if not text.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PDF contained no extractable text.")
        chunks = chunk_text(text)
        tags = ["upload", "pdf", _safe_tag(filename)]
        try:
            for chunk in chunks:
                rag_service.store(chunk, tags)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Memory store failed: {exc}",
            ) from exc
        preview = chunks[0][:240] if chunks else ""
        return MemoryUploadResponse(
            stored_chunks=len(chunks),
            filename=filename,
            kind="pdf",
            preview=preview,
        )

    if kind == "image":
        saved_name = _save_upload(filename, data)
        try:
            caption = _caption_image(data)
        except Exception as exc:
            # Keep the upload useful even when HF image-to-text is unavailable.
            print(f"[Memory] Image caption fallback | {type(exc).__name__}: {exc}")
            caption = (
                f"Visual asset for marketing context (filename hints: {Path(filename).stem.replace('_', ' ')}). "
                f"Auto-caption unavailable ({type(exc).__name__})."
            )
        content = f"Uploaded image '{filename}' ({saved_name}): {caption}"
        try:
            rag_service.store(content, ["upload", "image", _safe_tag(filename)])
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Memory store failed: {exc}",
            ) from exc
        return MemoryUploadResponse(
            stored_chunks=1,
            filename=filename,
            kind="image",
            preview=content[:240],
        )

    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="Unsupported file type. Use PDF, PNG, JPEG, or WebP.",
    )


def _detect_kind(filename: str, content_type: str) -> str | None:
    suffix = Path(filename).suffix.lower()
    if content_type in ALLOWED_PDF or suffix == ".pdf":
        return "pdf"
    if content_type in ALLOWED_IMAGES or suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return "image"
    return None


def _extract_pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="pypdf is not installed.",
        ) from exc

    from io import BytesIO

    try:
        reader = PdfReader(BytesIO(data))
        parts = [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid PDF: {exc}") from exc
    return "\n".join(parts)


def _save_upload(filename: str, data: bytes) -> str:
    uploads_dir = settings.uploads_dir
    uploads_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix.lower() or ".bin"
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", Path(filename).stem)[:40] or "upload"
    saved_name = f"{safe_stem}_{uuid4().hex[:8]}{suffix}"
    (uploads_dir / saved_name).write_bytes(data)
    return saved_name


def _caption_image(data: bytes) -> str:
    token = settings.hf_token.get_secret_value() if settings.hf_token else None
    hf = HuggingFaceService(
        hf_token=token,
        hf_model_id=settings.hf_model_id,
        hf_image_model_id=settings.hf_image_model_id,
        hf_caption_model_id=settings.hf_caption_model_id,
    )
    return hf.describe_image(data)


def _safe_tag(filename: str) -> str:
    tag = re.sub(r"[^a-zA-Z0-9_-]+", "_", filename).strip("_").lower()
    return tag[:48] or "file"
