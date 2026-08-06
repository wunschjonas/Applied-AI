"""Prometheus custom counters for Manager Chat / Agent graph.

Registered on the default prometheus_client registry so they appear on GET /metrics
alongside prometheus-fastapi-instrumentator HTTP metrics.
"""

from __future__ import annotations

from prometheus_client import Counter

REQUEST_STATUSES = frozenset(
    {"success", "partial_success", "needs_input", "error", "exception", "retrying"}
)
SPECIALIST_AGENTS = frozenset({"text", "image"})
SPECIALIST_STATUSES = frozenset({"success", "partial_success", "error"})
VALIDATION_RESULTS = frozenset(
    {"valid", "partial_success", "failed", "retry_text", "retry_image"}
)

manager_chat_requests_total = Counter(
    "manager_chat_requests_total",
    "Manager chat graph runs by final status",
    ["status"],
)
manager_chat_intent_total = Counter(
    "manager_chat_intent_total",
    "Manager chat intent classifications",
    ["intent"],
)
manager_chat_route_total = Counter(
    "manager_chat_route_total",
    "Manager chat intent-router destinations",
    ["target"],
)
manager_specialist_total = Counter(
    "manager_specialist_total",
    "Text/image specialist outcomes",
    ["agent", "status"],
)
manager_validation_total = Counter(
    "manager_validation_total",
    "Artifact validation decisions",
    ["result"],
)


def _label(value: str | None, allowed: frozenset[str] | None = None) -> str:
    raw = (value or "unknown").strip() or "unknown"
    # Prometheus label values should stay compact and alphanumeric-ish.
    cleaned = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in raw)[:64]
    if allowed is not None and cleaned not in allowed:
        return "other"
    return cleaned


def inc_manager_chat_request(status: str | None) -> None:
    manager_chat_requests_total.labels(status=_label(status, REQUEST_STATUSES)).inc()


def inc_manager_chat_intent(intent: str | None) -> None:
    manager_chat_intent_total.labels(intent=_label(intent)).inc()


def inc_manager_chat_route(target: str | None) -> None:
    manager_chat_route_total.labels(target=_label(target)).inc()


def inc_manager_specialist(agent: str | None, status: str | None) -> None:
    manager_specialist_total.labels(
        agent=_label(agent, SPECIALIST_AGENTS),
        status=_label(status, SPECIALIST_STATUSES),
    ).inc()


def inc_manager_validation(result: str | None) -> None:
    manager_validation_total.labels(result=_label(result, VALIDATION_RESULTS)).inc()
