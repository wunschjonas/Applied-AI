from fastapi import APIRouter, status

from app.schemas.post import PostCreate, PostResponse, PostUpdate
from app.services.post_service import PostService

router = APIRouter(prefix="/api/posts", tags=["posts"])

post_service = PostService()


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(post_create: PostCreate):
    return post_service.create_post(post_create)


@router.get("", response_model=list[PostResponse])
def list_posts():
    return post_service.list_posts()


@router.get("/{post_id}", response_model=PostResponse)
def get_post(post_id: str):
    return post_service.get_post(post_id)


@router.put("/{post_id}", response_model=PostResponse)
def update_post(post_id: str, post_update: PostUpdate):
    return post_service.update_post(post_id, post_update)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: str):
    post_service.delete_post(post_id)
    return None


@router.post("/{post_id}/generate-preview", response_model=PostResponse)
def generate_preview(post_id: str):
    return post_service.generate_preview(post_id)


@router.get("/{post_id}/preview")
def get_preview(post_id: str):
    return post_service.get_preview(post_id)


@router.get("/{post_id}/agent-trace")
def get_agent_trace(post_id: str):
    return post_service.get_agent_trace(post_id)