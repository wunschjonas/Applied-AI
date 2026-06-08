from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any


class JSONStore:
    def __init__(self, file_path: str | Path):
        self.path = Path(file_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()

        if not self.path.exists():
            self._write([])

    def _read(self) -> list[dict[str, Any]]:
        with self.lock:
            if not self.path.exists():
                self._write([])

            try:
                with self.path.open("r", encoding="utf-8") as file:
                    data = json.load(file)
                    return data if isinstance(data, list) else []
            except json.JSONDecodeError:
                return []

    def _write(self, data: list[dict[str, Any]]) -> None:
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")

        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)

        tmp_path.replace(self.path)

    def list(self) -> list[dict[str, Any]]:
        return self._read()

    def get(self, item_id: str) -> dict[str, Any] | None:
        return next((item for item in self._read() if item.get("id") == item_id), None)

    def save(self, document: dict[str, Any]) -> dict[str, Any]:
        items = self._read()
        index = next((i for i, item in enumerate(items) if item.get("id") == document.get("id")), None)

        if index is None:
            items.append(document)
        else:
            items[index] = document

        self._write(items)
        return document

    def delete(self, item_id: str) -> bool:
        items = self._read()
        filtered = [item for item in items if item.get("id") != item_id]

        if len(filtered) == len(items):
            return False

        self._write(filtered)
        return True