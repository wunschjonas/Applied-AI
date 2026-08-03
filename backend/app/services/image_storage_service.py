from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from app.core.config import settings


class ImageStorageService:
    content_type = "image/png"

    def __init__(self, storage_dir: Path | None = None):
        self.storage_dir = storage_dir or settings.generated_images_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save_png(self, image_bytes: bytes, filename_stem: str | None = None) -> dict[str, str]:
        if not image_bytes:
            raise ValueError("Cannot store an empty generated image.")

        filename = f"{filename_stem}.png" if filename_stem else f"{uuid4()}.png"
        if not self.is_safe_filename(filename):
            raise ValueError("Generated image filename is not safe.")

        path = self.storage_dir / filename
        path.write_bytes(image_bytes)

        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError("Generated image file was not written correctly.")

        return {
            "image_filename": filename,
            "image_url": f"/generated-images/{filename}",
            "image_content_type": self.content_type,
        }

    def read_bytes(self, filename: str | None) -> bytes | None:
        """Load a previously generated image if it exists on disk."""
        if not filename or not self.is_safe_filename(filename):
            return None
        path = self.storage_dir / filename
        if not path.exists() or not path.is_file() or path.stat().st_size == 0:
            return None
        return path.read_bytes()

    def read_post_image(self, post_id: str | None) -> bytes | None:
        if not post_id:
            return None
        return self.read_bytes(f"{post_id}.png")

    def exists(self, filename: str | None) -> bool:
        if not filename or not self.is_safe_filename(filename):
            return False
        path = self.storage_dir / filename
        return path.exists() and path.is_file() and path.stat().st_size > 0

    def is_safe_filename(self, filename: str) -> bool:
        return bool(re.fullmatch(r"[0-9a-fA-F-]{36}\.png", filename))
