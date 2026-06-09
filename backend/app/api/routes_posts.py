from fastapi import APIRouter, status

from app.schemas.post import PostCreate, PostInit, PostInitResponse, PostResponse, PostUpdate
from app.services.post_service import PostService

router = APIRouter(prefix="/api/posts", tags=["posts"])

post_service = PostService()


@router.post("/init", response_model=PostInitResponse, status_code=status.HTTP_201_CREATED)
def init_post(post_init: PostInit):
    print(f"[Posts] POST /api/posts/init aufgerufen | title='{post_init.title}'")
    return post_service.init_post(post_init)


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(post_create: PostCreate):
    print("[Posts] POST /api/posts aufgerufen")
    return post_service.create_post(post_create)


@router.get("", response_model=list[PostResponse])
def list_posts():
    print("[Posts] GET /api/posts aufgerufen")
    return post_service.list_posts()


@router.get("/{post_id}", response_model=PostResponse)
def get_post(post_id: str):
    print(f"[Posts] GET /api/posts/{post_id} aufgerufen")
    return post_service.get_post(post_id)


@router.put("/{post_id}", response_model=PostResponse)
def update_post(post_id: str, post_update: PostUpdate):
    print(f"[Posts] PUT /api/posts/{post_id} aufgerufen")
    return post_service.update_post(post_id, post_update)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: str):
    print(f"[Posts] DELETE /api/posts/{post_id} aufgerufen")
    post_service.delete_post(post_id)
    return None


@router.post("/{post_id}/generate-preview", response_model=PostResponse)
def generate_preview(post_id: str):
    print(f"[Posts] POST /api/posts/{post_id}/generate-preview aufgerufen")
    return post_service.generate_preview(post_id)


@router.get("/{post_id}/preview")
def get_preview(post_id: str):
    print(f"[Posts] GET /api/posts/{post_id}/preview aufgerufen")
    return post_service.get_preview(post_id)


@router.get("/{post_id}/agent-trace")
def get_agent_trace(post_id: str):
    print(f"[Posts] GET /api/posts/{post_id}/agent-trace aufgerufen")
    return post_service.get_agent_trace(post_id)