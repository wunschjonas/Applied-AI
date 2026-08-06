from fastapi import APIRouter, Query

from app.schemas.logs import AgentLogsDeleteResponse
from app.services.log_service import LogService

router = APIRouter(prefix="/api/logs", tags=["logs"])
log_service = LogService()


@router.delete("", response_model=AgentLogsDeleteResponse)
def delete_logs(post_id: str | None = Query(default=None)):
    """Delete all agent logs, or only logs for one post when post_id is set."""
    if post_id:
        deleted = log_service.delete_by_post_id(post_id)
        print(f"[Logs] DELETE /api/logs?post_id={post_id} | deleted={deleted}")
        return AgentLogsDeleteResponse(deleted=deleted, scope="post", post_id=post_id)

    deleted = log_service.delete_all()
    print(f"[Logs] DELETE /api/logs | deleted={deleted}")
    return AgentLogsDeleteResponse(deleted=deleted, scope="all", post_id=None)
