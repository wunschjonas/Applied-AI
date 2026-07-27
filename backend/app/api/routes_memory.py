from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.services.rag_service import RAGService

router = APIRouter(prefix="/api/memory", tags=["memory"])

rag_service = RAGService(memory_url=settings.mcp_memory_url)


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
