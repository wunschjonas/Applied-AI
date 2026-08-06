from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.storage.json_store import JSONStore

# Keep logs readable but allow full chat answers / tool snippets in the UI.
_LOG_INPUT_MAX = 500
_LOG_OUTPUT_MAX = 2000
_LOG_OBSERVATION_MAX = 2000


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
        thought: str | None = None,
        observation: str | None = None,
        output_summary: str | None = None,
        post_id: str | None = None,
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "id": str(uuid4()),
            "run_id": run_id or str(uuid4()),
            "agent": agent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step": step or action,
            "tool_called": tool_called,
            "thought": thought,
            "action": action,
            "observation": observation[:_LOG_OBSERVATION_MAX] if observation else None,
            "input_summary": input_summary[:_LOG_INPUT_MAX],
            "output_summary": output_summary[:_LOG_OUTPUT_MAX] if output_summary else None,
            "status": status,
            "duration_ms": duration_ms,
            "post_id": post_id,
        }
        self.store.save(entry)
        return entry

    def get_logs_by_agent(self, agent: str) -> list[dict[str, Any]]:
        return [entry for entry in self.store.list() if entry.get("agent") == agent]

    def delete_all(self) -> int:
        clear = getattr(self.store, "clear", None)
        if callable(clear):
            return int(clear())
        items = self.store.list()
        for item in items:
            item_id = item.get("id")
            if item_id:
                self.store.delete(item_id)
        return len(items)

    def delete_by_post_id(self, post_id: str) -> int:
        delete_where = getattr(self.store, "delete_where", None)
        if callable(delete_where):
            return int(delete_where(lambda entry: entry.get("post_id") == post_id))
        matches = [entry for entry in self.store.list() if entry.get("post_id") == post_id]
        for item in matches:
            item_id = item.get("id")
            if item_id:
                self.store.delete(item_id)
        return len(matches)
