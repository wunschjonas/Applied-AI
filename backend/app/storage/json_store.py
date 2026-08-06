from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any


class JSONStore:
    def __init__(self, file_path: str | Path):
        self.path = Path(file_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()

        if not self.path.exists():
            self._write([])

    def _read(self) -> list[dict[str, Any]]:
        """Read without locking — callers must already hold self.lock."""
        if not self.path.exists():
            self._write([])

        try:
            with self.path.open("r", encoding="utf-8") as file:
                data = json.load(file)
                return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            self._write([])
            return []

    def _write(self, data: list[dict[str, Any]]) -> None:
        """Write without locking — callers must already hold self.lock."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")

        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
            file.flush()

        tmp_path.replace(self.path)

    def list(self) -> list[dict[str, Any]]:
        with self.lock:
            return self._read()

    def get(self, item_id: str) -> dict[str, Any] | None:
        with self.lock:
            return next((item for item in self._read() if item.get("id") == item_id), None)

    def save(self, document: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            items = self._read()
            index = next(
                (i for i, item in enumerate(items) if item.get("id") == document.get("id")),
                None,
            )

            if index is None:
                items.append(document)
            else:
                items[index] = document

            self._write(items)
            return document

    def delete(self, item_id: str) -> bool:
        with self.lock:
            items = self._read()
            filtered = [item for item in items if item.get("id") != item_id]

            if len(filtered) == len(items):
                return False

            self._write(filtered)
            return True

    def clear(self) -> int:
        with self.lock:
            count = len(self._read())
            self._write([])
            return count

    def delete_where(self, predicate) -> int:
        """Remove items for which predicate(item) is True. Returns deleted count."""
        with self.lock:
            items = self._read()
            kept = [item for item in items if not predicate(item)]
            deleted = len(items) - len(kept)
            if deleted:
                self._write(kept)
            return deleted
