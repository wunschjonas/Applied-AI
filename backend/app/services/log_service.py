from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.storage.json_store import JSONStore


class LogService:
    def __init__(self):
        self.store = JSONStore(settings.agent_logs_file)

    def add_log(
        self,
        agent: str,
        action: str,
        input_summary: str,
        status: str,
        duration_ms: int,
        run_id: str | None = None,
        step: str | None = None,
        tool_called: str | None = None,
        decision: str | None = None,
        output_summary: str | None = None,
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "id": str(uuid4()),
            "run_id": run_id or str(uuid4()),
            "agent": agent,
            "timestamp": datetime.utcnow().isoformat(),
            "step": step or action,
            "tool_called": tool_called,
            "decision": decision,
            "action": action,
            "input_summary": input_summary[:300],
            "output_summary": output_summary[:300] if output_summary else None,
            "status": status,
            "duration_ms": duration_ms,
        }
        self.store.save(entry)
        return entry

    def get_logs_by_agent(self, agent: str) -> list[dict[str, Any]]:
        return [entry for entry in self.store.list() if entry.get("agent") == agent]
