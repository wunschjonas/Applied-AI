from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from app.core.config import settings
from app.storage.json_store import JSONStore


class TraceService:
    def __init__(self):
        self.store = JSONStore(settings.traces_file)

    def create_trace(self, chat_id: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        trace_id = str(uuid4())
        trace = {
            "id": trace_id,
            "trace_id": trace_id,
            "chat_id": chat_id,
            "created_at": datetime.utcnow().isoformat(),
            "steps": [],
            "metadata": metadata or {},
        }
        self.store.save(trace)
        return trace

    def add_step(
        self,
        trace: dict[str, Any],
        agent: str,
        decision: str,
        action: str,
        observation: str,
        status_value: str = "success",
    ) -> dict[str, Any]:
        step = {
            "index": len(trace["steps"]) + 1,
            "agent": agent,
            "decision": decision,
            "action": action,
            "observation": observation,
            "status": status_value,
            "timestamp": datetime.utcnow().isoformat(),
        }
        trace["steps"].append(step)
        self.store.save(trace)
        return step

    def get_trace(self, trace_id: str) -> dict[str, Any]:
        trace = next((item for item in self.store.list() if item.get("trace_id") == trace_id), None)

        if not trace:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found")

        return trace
