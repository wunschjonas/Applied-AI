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
    ) -> dict[str, Any]:
        entry = {
            "id": str(uuid4()),
            "agent": agent,
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "input_summary": input_summary[:200],
            "status": status,
            "duration_ms": duration_ms,
        }
        self.store.save(entry)
        return entry

    def get_logs_by_agent(self, agent: str) -> list[dict[str, Any]]:
        return [entry for entry in self.store.list() if entry.get("agent") == agent]
