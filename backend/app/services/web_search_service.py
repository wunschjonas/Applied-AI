"""Lightweight web search for manager ReAct (optional dependency)."""

from __future__ import annotations

import logging
import re
from typing import Any, Callable

from app.core.config import settings

logger = logging.getLogger(__name__)

_QUESTION_NOISE = re.compile(
    r"(?i)\b(?:wer|was|wie|wo|wann|warum|wieso|weshalb|welche[rs]?|"
    r"hat|haben|ist|sind|wurde|wurden|gewonnen|gewann)\b"
)


def web_search_enabled() -> bool:
    return bool(getattr(settings, "web_search_enabled", True))


def _keywordize(query: str) -> str:
    """Turn a full question into denser keywords for metasearch backends."""
    cleaned = re.sub(r"[?!.]+", " ", query)
    cleaned = _QUESTION_NOISE.sub(" ", cleaned)
    tokens = [t for t in re.split(r"\s+", cleaned) if len(t) > 1]
    return " ".join(tokens).strip() or query.strip()


def _format_results(results: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for index, item in enumerate(results, start=1):
        title = (item.get("title") or "").strip()
        body = (item.get("body") or item.get("snippet") or "").strip()
        href = (item.get("href") or item.get("link") or "").strip()
        piece = f"{index}. {title}: {body}".strip()
        if href:
            piece = f"{piece} ({href})"
        if piece:
            lines.append(piece[:280])
    return "\n".join(lines)


def _load_ddgs_factory() -> Callable[[], Any] | None:
    try:
        from ddgs import DDGS  # type: ignore

        return DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS  # type: ignore

            logger.warning(
                "Using deprecated duckduckgo_search; install `ddgs` for reliable results"
            )
            return DDGS
        except ImportError:
            return None


def _run_search(
    ddgs_cls: Callable[[], Any],
    query: str,
    max_results: int,
    *,
    backend: str = "auto",
) -> list[dict[str, Any]]:
    kwargs: dict[str, Any] = {
        "region": "de-de",
        "max_results": max_results,
    }
    # New `ddgs` accepts backend=; old package may ignore or differ.
    try:
        with ddgs_cls() as client:
            return list(client.text(query, backend=backend, **kwargs)) or []
    except TypeError:
        with ddgs_cls() as client:
            return list(client.text(query, **kwargs)) or []


def search_web(query: str, max_results: int = 3) -> str:
    """Return short text snippets for a query. Empty string if disabled/unavailable."""
    if not web_search_enabled():
        return ""
    query = (query or "").strip()
    if not query:
        return ""
    max_results = max(1, min(int(max_results or 3), 5))

    ddgs_cls = _load_ddgs_factory()
    if ddgs_cls is None:
        logger.warning("ddgs not installed; web_search unavailable")
        return ""

    attempts = [
        (query, "auto"),
        (_keywordize(query), "auto"),
        (_keywordize(query) or query, "bing,duckduckgo,wikipedia"),
    ]
    seen: set[str] = set()
    last_error: Exception | None = None

    for attempt_query, backend in attempts:
        key = f"{attempt_query}|{backend}"
        if not attempt_query or key in seen:
            continue
        seen.add(key)
        try:
            results = _run_search(ddgs_cls, attempt_query, max_results, backend=backend)
        except Exception as exc:
            last_error = exc
            logger.warning(
                "web_search attempt failed (%s / %s): %s",
                attempt_query,
                backend,
                exc,
            )
            continue
        if results:
            return _format_results(results)

    if last_error is not None:
        raise last_error
    return ""
