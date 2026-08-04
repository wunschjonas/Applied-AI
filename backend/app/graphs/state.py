from __future__ import annotations

from typing import Any, TypedDict


class ManagerChatState(TypedDict, total=False):
    post_id: str
    chat_id: str | None
    trace_id: str
    trace: dict[str, Any]
    chat: dict[str, Any]
    user_message: str
    context: str | dict[str, Any] | None
    intent: str
    rag_needed: bool
    rag_context: str | None
    used_agents: list[str]
    generated_artifacts: dict[str, Any]
    assistant_message: str
    trace_steps: list[dict[str, Any]]
    errors: list[str]
    warnings: list[str]
    status: str
    platform: str | None
    text_retry_count: int
    image_retry_count: int
    validation_feedback: dict[str, Any]
    validation_result: str
    execution_plan: dict[str, Any]
    post: dict[str, Any] | None
    post_data_updates: dict[str, Any]
    post_data_missing: list[str]
    post_data_blocking: list[str]
    explicit_generate: bool
    followup_question: str | None
    # Manager ReAct tool side-effects
    tools_called: list[str]
    post_data_checked: bool
    post_data_complete: bool | None
    post_data_incomplete_from_tool: bool
    web_context: str | None
    tool_safety_blocked: bool
    stored_preview: str | None
    stored_tags: list[str]
