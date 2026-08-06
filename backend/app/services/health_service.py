from __future__ import annotations

import socket
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.core.config import settings

SERVICE_NAME = "applied-ai-marketing-agent"
MEMORY_CHECK_TIMEOUT_SECONDS = 2.0


def _component(status: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": status}
    payload.update(extra)
    return payload


def _check_storage() -> dict[str, Any]:
    data_dir = Path(settings.data_dir)
    posts_file = Path(settings.posts_file)
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        writable = data_dir.is_dir() and data_dir.exists()
        # Touch-check: parent of posts file must be writable.
        probe = data_dir / ".health_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        posts_parent_ok = posts_file.parent.exists() or writable
        if writable and posts_parent_ok:
            return _component(
                "up",
                data_dir=str(data_dir),
                posts_file=str(posts_file),
                detail="storage paths available",
            )
        return _component("down", detail="storage directory not usable")
    except OSError as exc:
        return _component("down", detail=f"{type(exc).__name__}: {exc}")


def _check_memory() -> dict[str, Any]:
    """Probe MCP reachability via TCP only — avoids streamable-HTTP 406 spam on GET."""
    url = str(settings.mcp_memory_url).rstrip("/")
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    if parsed.port is not None:
        port = parsed.port
    elif parsed.scheme == "https":
        port = 443
    else:
        port = 80

    try:
        with socket.create_connection((host, port), timeout=MEMORY_CHECK_TIMEOUT_SECONDS):
            pass
        return _component(
            "up",
            url=url,
            host=host,
            port=port,
            detail="memory host reachable (tcp)",
        )
    except OSError as exc:
        return _component(
            "down",
            url=url,
            host=host,
            port=port,
            detail=f"{type(exc).__name__}: {exc}",
        )


def _check_huggingface() -> dict[str, Any]:
    token = settings.hf_token
    configured = bool(token and token.get_secret_value())
    return {
        "configured": configured,
        "model_id": settings.hf_model_id,
        "image_model_id": settings.hf_image_model_id,
        "detail": "HF_TOKEN set" if configured else "HF_TOKEN not set",
    }


def _check_web_search() -> dict[str, Any]:
    return {
        "enabled": bool(settings.web_search_enabled),
        "detail": "web search enabled" if settings.web_search_enabled else "web search disabled",
    }


def build_health_report() -> dict[str, Any]:
    """JSON health overview for /health — values come from settings + live checks."""
    storage = _check_storage()
    memory = _check_memory()
    huggingface = _check_huggingface()
    web_search = _check_web_search()

    critical_ok = storage.get("status") == "up" and memory.get("status") == "up"
    overall = "ok" if critical_ok else "degraded"

    return {
        "status": overall,
        "service": SERVICE_NAME,
        "version": settings.app_version,
        "components": {
            "storage": storage,
            "memory": memory,
            "huggingface": huggingface,
            "web_search": web_search,
        },
    }
