from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.schemas.chat import _strip_nonempty
from app.services.huggingface_service import HuggingFaceService
from app.services.rag_service import RAGService, chunk_text

router = APIRouter(prefix="/api/memory", tags=["memory"])

rag_service = RAGService(memory_url=settings.mcp_memory_url)

ALLOWED_PDF = {
    "application/pdf",
    "application/x-pdf",
    "application/acrobat",
    "applications/vnd.pdf",
}
ALLOWED_IMAGES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
PDF_MAGIC = b"%PDF"


class MemoryStoreRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    tags: list[str] = []

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, value: object) -> object:
        if isinstance(value, str):
            return _strip_nonempty(value, max_length=20000)
        return value


class MemoryStoreResponse(BaseModel):
    status: str


class MemorySearchResponse(BaseModel):
    query: str
    results: list[str]


class MemoryListEntry(BaseModel):
    content: str
    content_hash: str
    tags: list[str] = []


class MemoryListResponse(BaseModel):
    entries: list[MemoryListEntry]


class MemoryUploadResponse(BaseModel):
    stored_chunks: int
    filename: str
    kind: str
    preview: str


class MemoryDeleteResponse(BaseModel):
    status: str
    content_hash: str


@router.post("/store", response_model=MemoryStoreResponse, status_code=status.HTTP_201_CREATED)
def store_memory(body: MemoryStoreRequest):
    print(f"[Memory] POST /api/memory/store | content='{body.content[:60]}...'")
    try:
        rag_service.store(body.content, body.tags)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return MemoryStoreResponse(status="stored")


@router.get("/search", response_model=MemorySearchResponse)
def search_memory(q: str = Query(..., min_length=1, max_length=4000)):
    query = q.strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="q must not be empty or whitespace-only",
        )
    print(f"[Memory] GET /api/memory/search | q='{query}'")
    raw = rag_service.retrieve(query)
    results = [line for line in raw.splitlines() if line.strip()] if raw else []
    return MemorySearchResponse(query=query, results=results)


@router.get("/list", response_model=MemoryListResponse)
def list_memory():
    print("[Memory] GET /api/memory/list")
    entries = [
        MemoryListEntry(
            content=entry.get("content") or "",
            content_hash=entry.get("content_hash") or "",
            tags=list(entry.get("tags") or []),
        )
        for entry in rag_service.list_entries()
        if entry.get("content")
    ]
    return MemoryListResponse(entries=entries)


@router.delete("/{content_hash}", response_model=MemoryDeleteResponse)
def delete_memory(content_hash: str):
    print(f"[Memory] DELETE /api/memory/{content_hash[:16]}...")
    try:
        deleted = rag_service.delete(content_hash)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory entry not found or not deleted.")
    return MemoryDeleteResponse(status="deleted", content_hash=content_hash)


@router.post("/upload", response_model=MemoryUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_memory(file: UploadFile = File(...)):
    filename = Path(file.filename or "upload.bin").name.strip()
    content_type = (file.content_type or "").lower().split(";", 1)[0].strip()
    print(f"[Memory] POST /api/memory/upload | filename='{filename}' type='{content_type}'")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large (max 15MB).")

    kind = _detect_kind(filename, content_type, data)
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
        detail=(
            "Unsupported file type. Use PDF, PNG, JPEG, or WebP. "
            f"(got filename='{filename}', content_type='{content_type or 'unknown'}')"
        ),
    )


def _detect_kind(filename: str, content_type: str, data: bytes | None = None) -> str | None:
    suffix = Path(filename.strip()).suffix.lower().strip()
    mime = (content_type or "").lower().split(";", 1)[0].strip()

    if mime in ALLOWED_PDF or suffix == ".pdf":
        return "pdf"
    if mime in ALLOWED_IMAGES or suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return "image"

    # Browsers sometimes send application/octet-stream or omit the extension in transit.
    if data:
        if data[:4] == PDF_MAGIC:
            return "pdf"
        if data.startswith(b"\x89PNG\r\n\x1a\n") or data[:3] == b"\xff\xd8\xff":
            return "image"
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "image"
        if mime == "application/octet-stream" and b"/Type /Catalog" in data[:2048]:
            return "pdf"

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
        timeout=settings.hf_timeout_seconds,
        image_timeout=settings.hf_image_timeout_seconds,
    )
    return hf.describe_image(data)


def _safe_tag(filename: str) -> str:
    tag = re.sub(r"[^a-zA-Z0-9_-]+", "_", filename).strip("_").lower()
    return tag[:48] or "file"
