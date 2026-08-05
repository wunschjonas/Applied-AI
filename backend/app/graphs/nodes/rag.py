from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.graphs.dependencies import GraphDependencies, StepRecorder
from app.graphs.state import ManagerChatState
from app.graphs.support.post_data_llm import try_hf
from app.graphs.support.manager_tools import (
    MANAGER_TOOLS,
    ManagerToolDispatcher,
    resolve_memory_store_content,
    suggest_memory_tags,
)
from app.graphs.support.post_fields import (
    is_memory_inquiry,
    is_memory_store_request,
    memory_search_query,
)
from app.graphs.support.tao_composer import TaoEvent
from app.services.web_search_service import search_web, web_search_enabled


MAX_TOOL_ROUNDS = 3

REACT_SYSTEM_PROMPT = """You are the tool planner for a marketing multi-agent system.
You choose zero or more tools, then stop when you have enough context.

Tools:
- check_post_data_completeness: BEFORE text/image generation, check required post Steckbrief fields.
- get_post_data: read current post Steckbrief/preview.
- memory_search: search internal brand/project memory (on-topic only).
- memory_list: overview of stored memory; use for "what do you know" or empty search.
- memory_store: save a durable fact ONLY if the user asks to remember/save something.
  If they say "speicher den Fakt" / "store this" without repeating it, set content to the
  PREVIOUS user message (the actual fact). Never store the store-command text itself.
- web_search: current public facts, news, trends, or events not in project memory.

Rules:
- Factual / knowledge questions (e.g. "do you know who…", "who won…") without a generate-post request:
  call memory_search first with topical keywords. If empty, call web_search with topical keywords.
- Explicit web/internet search requests: call web_search (keywords from the full question).
- Generation intents that need timely world knowledge: web_search first; completeness only if generating this turn.
- Do NOT call check_post_data_completeness when answering a knowledge/research question (no post generation).
- Tool queries must be topical keywords (topic + year + event), NEVER a lone pronoun like "wer"/"was"/"wie".
- Internal brand facts / PDFs: memory_*; public timely facts: web_search.
- If a tool fails or returns empty, try a different tool or reformulate the query once.
- Do not dump chain-of-thought; keep tool arguments short.
- At most a few useful tool calls; then stop (no more tools)."""


class RagNodes:
    def __init__(self, deps: GraphDependencies):
        self.deps = deps
        self.recorder = StepRecorder(deps)
        self.dispatcher = ManagerToolDispatcher(
            rag_service=deps.rag_service,
            post_repository=deps.post_repository,
            web_search=search_web if web_search_enabled() else None,
        )

    def rag_react_node(self, state: ManagerChatState) -> ManagerChatState:
        """LLM-native ReAct loop over manager tools."""
        started_at = datetime.utcnow()
        state["rag_needed"] = False
        state["rag_context"] = None
        state["web_context"] = None
        state["tools_called"] = []
        state["post_data_checked"] = False
        state["post_data_complete"] = None
        state["post_data_incomplete_from_tool"] = False
        state["tool_safety_blocked"] = False

        if state.get("intent") == "post_status_inquiry":
            # Still allow optional brief read via tools when HF available.
            pass

        hf = try_hf(self.deps.hf_factory)
        if hf is None:
            if self._wants_memory_store(state):
                return self._forced_memory_store(state, started_at)
            if state.get("intent") == "memory_inquiry" or is_memory_inquiry(state["user_message"]):
                return self._forced_memory_search(state, started_at)
            return self._keyword_fallback(state, started_at, reason="HF unavailable for tool calling")

        messages = [
            {"role": "system", "content": REACT_SYSTEM_PROMPT},
            {"role": "user", "content": self._user_prompt(state)},
        ]

        try:
            for round_index in range(MAX_TOOL_ROUNDS):
                result = hf.chat_with_tools(
                    messages=messages,
                    tools=MANAGER_TOOLS,
                    max_tokens=350,
                    temperature=0.2,
                )
                tool_calls = result.get("tool_calls") or []

                if not tool_calls:
                    event = TaoEvent(
                        phase="manager_tool",
                        node="rag_react_node",
                        agent="rag_react_node",
                        status="skipped",
                        intent=state.get("intent"),
                        facts={
                            "rag_mode": "skip",
                            "skipped": True,
                            "round": round_index + 1,
                            "detail": "Modell hat keinen weiteren Tool-Aufruf gewählt.",
                            "tools_called": list(state.get("tools_called") or []),
                        },
                    )
                    self.recorder.record(state, event)
                    break

                assistant_message: dict[str, Any] = {
                    "role": "assistant",
                    "content": result.get("content"),
                    "tool_calls": [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {
                                "name": call["name"],
                                "arguments": json.dumps(call.get("arguments") or {}),
                            },
                        }
                        for call in tool_calls
                    ],
                }
                messages.append(assistant_message)

                for call in tool_calls:
                    name = call.get("name") or ""
                    args = call.get("arguments") or {}
                    observation, status, effects = self.dispatcher.dispatch(name, args, state)
                    self._apply_effects(state, effects)
                    if name:
                        state.setdefault("tools_called", []).append(name)

                    event = TaoEvent(
                        phase="manager_tool",
                        node="rag_react_node",
                        agent="rag_react_node",
                        status=status,
                        intent=state.get("intent"),
                        facts={
                            "rag_mode": "llm",
                            "tool_name": name,
                            "query": effects.get("query"),
                            "rag_hit_count": effects.get("rag_hit_count"),
                            "web_hit_count": effects.get("web_hit_count"),
                            "post_data_missing": effects.get("post_data_missing"),
                            "post_data_complete": effects.get("post_data_complete"),
                            "rag_summary": observation,
                            "tool_error": effects.get("tool_error"),
                            "round": round_index + 1,
                        },
                    )
                    self.recorder.record(state, event)
                    self.recorder.log(
                        state,
                        agent="manager_agent",
                        status="success" if status == "success" else "skipped",
                        step="manager_react",
                        started_at=started_at,
                        tool_called=name or None,
                        event=event,
                        output_summary=(observation or "")[:300],
                    )

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "name": name,
                            "content": observation,
                        }
                    )

            done = TaoEvent(
                phase="rag_done",
                node="rag_react_node",
                agent="rag_react_node",
                status="success" if (state.get("rag_context") or state.get("web_context") or state.get("post_data_checked")) else "skipped",
                intent=state.get("intent"),
                facts={
                    "rag_needed": bool(state.get("rag_context")),
                    "rag_hit_count": self._hit_count(state.get("rag_context")),
                    "tools_called": list(state.get("tools_called") or []),
                },
            )
            self.recorder.log(
                state,
                agent="manager_agent",
                status=done.status,
                step="manager_react_done",
                started_at=started_at,
                event=done,
                output_summary=f"tools={state.get('tools_called')}",
            )
            return state
        except Exception as exc:
            warning = f"Tool-calling loop failed safely: {type(exc).__name__}: {exc}"
            state["warnings"].append(warning)
            if self._wants_memory_store(state):
                return self._forced_memory_store(state, started_at)
            if state.get("intent") == "memory_inquiry" or is_memory_inquiry(state["user_message"]):
                return self._forced_memory_search(state, started_at)
            return self._keyword_fallback(state, started_at, reason=warning)

    def _apply_effects(self, state: ManagerChatState, effects: dict[str, Any]) -> None:
        if "rag_context" in effects:
            state["rag_context"] = effects["rag_context"]
        if effects.get("rag_needed"):
            state["rag_needed"] = True
        if effects.get("web_context"):
            existing = state.get("web_context")
            state["web_context"] = (
                f"{existing}\n{effects['web_context']}".strip() if existing else effects["web_context"]
            )
        if effects.get("post_data_checked"):
            state["post_data_checked"] = True
            state["post_data_complete"] = bool(effects.get("post_data_complete"))
            missing = effects.get("post_data_missing") or []
            state["post_data_incomplete_from_tool"] = bool(missing)
            if missing:
                state["post_data_blocking"] = list(missing)
                state["post_data_missing"] = list(dict.fromkeys([*(state.get("post_data_missing") or []), *missing]))
        if effects.get("stored_preview"):
            state["stored_preview"] = str(effects["stored_preview"])
        if effects.get("stored_tags"):
            state["stored_tags"] = list(effects["stored_tags"])

    @staticmethod
    def _wants_memory_store(state: ManagerChatState) -> bool:
        return state.get("intent") == "memory_store" or is_memory_store_request(state["user_message"])

    def _forced_memory_store(self, state: ManagerChatState, started_at: datetime) -> ManagerChatState:
        """Fallback when HF tools unavailable for an explicit memory-store request."""
        content = resolve_memory_store_content(
            str(state.get("user_message") or ""),
            user_message=state.get("user_message"),
            chat=state.get("chat"),
        )
        tags = suggest_memory_tags(content)
        observation, status, effects = self.dispatcher.dispatch(
            "memory_store",
            {"content": content, "tags": tags},
            state,
        )
        self._apply_effects(state, effects)
        state.setdefault("tools_called", []).append("memory_store")

        event = TaoEvent(
            phase="manager_tool",
            node="rag_react_node",
            agent="rag_react_node",
            status=status,
            intent=state.get("intent"),
            facts={
                "rag_mode": "forced",
                "tool_name": "memory_store",
                "rag_summary": observation,
                "stored_preview": effects.get("stored_preview") or state.get("stored_preview"),
                "stored_tags": effects.get("stored_tags") or state.get("stored_tags"),
            },
        )
        self.recorder.record(state, event)
        self.recorder.log(
            state,
            agent="manager_agent",
            status="success" if status == "success" else "skipped",
            step="manager_react_forced",
            started_at=started_at,
            tool_called="memory_store",
            event=event,
            output_summary=observation[:300],
        )
        return state

    def _forced_memory_search(self, state: ManagerChatState, started_at: datetime) -> ManagerChatState:
        """Fallback when HF tools unavailable for memory Q&A."""
        query = memory_search_query(state["user_message"])
        observation, status, effects = self.dispatcher.dispatch(
            "memory_search",
            {"query": query, "n_results": 5},
            state,
        )
        self._apply_effects(state, effects)
        state.setdefault("tools_called", []).append("memory_search")

        if not state.get("rag_context"):
            observation2, status2, effects2 = self.dispatcher.dispatch("memory_list", {"limit": 15}, state)
            self._apply_effects(state, effects2)
            state["tools_called"].append("memory_list")
            observation = f"{observation} | {observation2}"
            status = status2 if state.get("rag_context") else status

        event = TaoEvent(
            phase="manager_tool",
            node="rag_react_node",
            agent="rag_react_node",
            status=status,
            intent=state.get("intent"),
            facts={
                "rag_mode": "forced",
                "tool_name": "memory_search",
                "query": query,
                "rag_hit_count": self._hit_count(state.get("rag_context")),
                "rag_summary": observation,
            },
        )
        self.recorder.record(state, event)
        self.recorder.log(
            state,
            agent="manager_agent",
            status="success" if status == "success" else "skipped",
            step="manager_react_forced",
            started_at=started_at,
            tool_called="mcp_memory_search",
            event=event,
            output_summary=observation[:300],
        )
        return state

    def _keyword_fallback(
        self,
        state: ManagerChatState,
        started_at: datetime,
        reason: str,
    ) -> ManagerChatState:
        # Soft completeness signal for generate intents when tools unavailable.
        if state.get("intent") in {"text_only", "image_only", "text_and_image"} and state.get("post_data_blocking"):
            state["post_data_incomplete_from_tool"] = True

        rag_needed = self.deps.rag_service.is_needed(state["user_message"])
        state["rag_needed"] = rag_needed
        if not rag_needed:
            observation = f"{reason}. Keyword-Fallback überspringt Abruf."
            event = TaoEvent(
                phase="manager_tool",
                node="rag_react_node",
                agent="rag_react_node",
                status="skipped",
                intent=state.get("intent"),
                facts={"rag_mode": "fallback", "skipped": True, "detail": observation},
            )
            self.recorder.record(state, event)
            self.recorder.log(
                state,
                agent="manager_agent",
                status="skipped",
                step="manager_react_fallback",
                started_at=started_at,
                event=event,
            )
            return state

        observation, status, effects = self.dispatcher.dispatch(
            "memory_search",
            {"query": self._default_search_query(state)},
            state,
        )
        self._apply_effects(state, effects)
        state.setdefault("tools_called", []).append("memory_search")
        event = TaoEvent(
            phase="manager_tool",
            node="rag_react_node",
            agent="rag_react_node",
            status=status,
            intent=state.get("intent"),
            facts={
                "rag_mode": "fallback",
                "tool_name": "memory_search",
                "query": effects.get("query"),
                "rag_hit_count": effects.get("rag_hit_count"),
                "rag_summary": observation,
            },
        )
        self.recorder.record(state, event)
        self.recorder.log(
            state,
            agent="manager_agent",
            status="success" if status == "success" else "skipped",
            step="manager_react_fallback",
            started_at=started_at,
            tool_called="mcp_memory_search",
            event=event,
            output_summary=observation[:300],
        )
        return state

    @staticmethod
    def _hit_count(rag_context: str | None) -> int:
        if not rag_context:
            return 0
        return len([line for line in rag_context.splitlines() if line.strip()])

    @staticmethod
    def _default_search_query(state: ManagerChatState) -> str:
        post = state.get("post") or {}
        topic = str(post.get("topic") or "").strip()
        message = str(state.get("user_message") or "").strip()
        if topic and message:
            return f"{topic} {message[:80]}".strip()
        return topic or message

    @staticmethod
    def _user_prompt(state: ManagerChatState) -> str:
        post = state.get("post") or {}
        brief = {
            "topic": post.get("topic"),
            "platform": post.get("platform"),
            "target_audience": post.get("target_audience"),
            "tone_of_voice": post.get("tone_of_voice"),
            "text_context": post.get("text_context"),
            "text_length": post.get("text_length"),
            "image_context": post.get("image_context"),
            "image_style": post.get("image_style"),
        }
        intent = state.get("intent") or "unknown"
        missing = state.get("post_data_blocking") or []
        history_lines: list[str] = []
        for item in (state.get("chat") or {}).get("messages") or []:
            role = str(item.get("role") or "").upper()
            content = str(item.get("content") or "").strip()
            if role in {"USER", "AGENT"} and content:
                history_lines.append(f"{role}: {content[:500]}")
        recent = "\n".join(history_lines[-6:]) or "(none)"
        return (
            f"Recent chat (oldest→newest):\n{recent}\n\n"
            f"Current user message:\n{state['user_message']}\n\n"
            f"Intent: {intent}\n"
            f"Known missing required fields (may be stale until check_post_data_completeness): {missing}\n"
            f"Steckbrief snapshot:\n{json.dumps(brief, ensure_ascii=False)}\n\n"
            "Choose tools as needed, then stop."
        )

    def rag_decision_node(self, state: ManagerChatState) -> ManagerChatState:
        return self.rag_react_node(state)

    def rag_retrieval_node(self, state: ManagerChatState) -> ManagerChatState:
        return state
