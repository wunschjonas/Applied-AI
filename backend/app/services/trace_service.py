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
        if settings.tao_verbose:
            print(f"===== TAO RUN START | trace_id={trace_id} | chat_id={chat_id or '-'} =====")
        return trace

    def add_step(
        self,
        trace: dict[str, Any],
        agent: str,
        thought: str,
        action: str,
        observation: str,
        status_value: str = "success",
    ) -> dict[str, Any]:
        step = {
            "index": len(trace["steps"]) + 1,
            "agent": agent,
            "thought": thought,
            "action": action,
            "observation": observation,
            "status": status_value,
            "timestamp": datetime.utcnow().isoformat(),
        }
        trace["steps"].append(step)
        self.store.save(trace)
        if settings.tao_verbose:
            print(
                f"[TAO {step['index']:02d}] agent={agent}  status={status_value}\n"
                f"  Thought:     {thought}\n"
                f"  Action:      {action}\n"
                f"  Observation: {observation}"
            )
        return step

    def print_run_footer(self, trace: dict[str, Any], status: str = "success") -> None:
        if not settings.tao_verbose:
            return
        metadata = trace.get("metadata") or {}
        print(
            f"===== TAO RUN END | steps={len(trace.get('steps', []))} | "
            f"status={status} | used_agents={metadata.get('used_agents', [])} | "
            f"retry_count={metadata.get('retry_count', {})} ====="
        )

    def get_trace(self, trace_id: str) -> dict[str, Any]:
        trace = next((item for item in self.store.list() if item.get("trace_id") == trace_id), None)

        if not trace:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found")

        return trace
