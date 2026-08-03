from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.graphs.dependencies import GraphDependencies, StepRecorder
from app.graphs.state import ManagerChatState
from app.graphs.support.brief_llm import try_hf
from app.graphs.support.post_fields import is_memory_inquiry, memory_search_query
from app.services.rag_service import MEMORY_SEARCH_TOOL


MAX_TOOL_ROUNDS = 2

REACT_SYSTEM_PROMPT = """You are the retrieval planner for a marketing multi-agent system.
You may call the memory_search tool when stored brand facts, uploaded PDFs, images, or prior notes
could help. If the user asks what is stored in memory/RAG/Gedaechtnis, you MUST call memory_search.
If the user message and brief already contain enough information for normal generation,
do not call any tool — reply briefly that no memory search is needed.
Prefer a short, focused search query. At most one useful search is enough in most cases."""


class RagNodes:
    def __init__(self, deps: GraphDependencies):
        self.deps = deps
        self.recorder = StepRecorder(deps)

    def rag_react_node(self, state: ManagerChatState) -> ManagerChatState:
        """LLM-native ReAct loop: Thought → memory_search Action → Observation."""
        started_at = datetime.utcnow()
        state["rag_needed"] = False
        state["rag_context"] = None

        # Memory Q&A: always retrieve (tool loop or direct search), never skip silently.
        if state.get("intent") == "post_status_inquiry":
            return state
        if state.get("intent") == "memory_inquiry" or is_memory_inquiry(state["user_message"]):
            return self._forced_memory_search(state, started_at)

        hf = try_hf(self.deps.hf_factory)
        if hf is None:
            return self._keyword_fallback(state, started_at, reason="HF unavailable for tool calling")

        messages = [
            {"role": "system", "content": REACT_SYSTEM_PROMPT},
            {"role": "user", "content": self._user_prompt(state)},
        ]
        observations: list[str] = []

        try:
            for round_index in range(MAX_TOOL_ROUNDS):
                result = hf.chat_with_tools(
                    messages=messages,
                    tools=[MEMORY_SEARCH_TOOL],
                    max_tokens=300,
                    temperature=0.2,
                )
                tool_calls = result.get("tool_calls") or []
                thought = result.get("content") or (
                    f"Planning retrieval round {round_index + 1}."
                    if tool_calls
                    else "Model decided no memory search is needed."
                )

                if not tool_calls:
                    self.recorder.step(
                        state,
                        "rag_react_node",
                        thought,
                        "skip_memory_search",
                        "No tool_calls; RAG skipped.",
                        "skipped",
                    )
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
                    if name != "memory_search":
                        observation = f"Unsupported tool '{name}' ignored."
                        status = "warning"
                        state["warnings"].append(observation)
                    else:
                        observation, status = self._run_memory_search(state, call.get("arguments") or {})
                        if status == "success" and observation:
                            observations.append(observation)

                    self.recorder.step(
                        state,
                        "rag_react_node",
                        thought,
                        "call_memory_search",
                        observation,
                        status,
                    )
                    self.recorder.log(
                        state,
                        agent="manager_agent",
                        status="success" if status == "success" else "skipped",
                        step="rag_react",
                        started_at=started_at,
                        tool_called="mcp_memory_search",
                        thought=thought,
                        observation=observation,
                        output_summary=observation[:300],
                    )

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "name": name,
                            "content": observation,
                        }
                    )

            if state.get("rag_context"):
                final_observation = f"ReAct RAG finished with {len(observations)} tool observation(s)."
                final_status = "success"
            else:
                final_observation = "ReAct RAG finished without memory context."
                final_status = "skipped"

            self.recorder.log(
                state,
                agent="manager_agent",
                status=final_status,
                step="rag_react_done",
                started_at=started_at,
                thought="Completed memory_search ReAct loop.",
                observation=final_observation,
                output_summary=final_observation,
            )
            return state
        except Exception as exc:
            warning = f"Tool-calling RAG failed safely: {type(exc).__name__}: {exc}"
            state["warnings"].append(warning)
            return self._keyword_fallback(state, started_at, reason=warning)

    def _forced_memory_search(self, state: ManagerChatState, started_at: datetime) -> ManagerChatState:
        """Always retrieve for memory Q&A; fall back to memory_list if search is empty."""
        query = memory_search_query(state["user_message"])
        observation, status = self._run_memory_search(state, {"query": query, "n_results": 5})
        if not state.get("rag_context"):
            entries = self.deps.rag_service.list_all()
            if entries:
                state["rag_context"] = "\n".join(entries[:8])
                state["rag_needed"] = True
                observation = f"memory_list fallback returned {len(entries)} entr(y/ies)."
                status = "success"
            else:
                observation = f"{observation} memory_list also empty."
                status = "warning"

        self.recorder.step(
            state,
            "rag_react_node",
            f"Forced memory retrieval for query '{query}'.",
            "call_memory_search",
            observation,
            status,
        )
        self.recorder.log(
            state,
            agent="manager_agent",
            status="success" if status == "success" else "skipped",
            step="rag_react_forced",
            started_at=started_at,
            tool_called="mcp_memory_search",
            thought=f"Forced memory retrieval for query '{query}'.",
            observation=observation,
            output_summary=observation[:300],
        )
        return state

    def _run_memory_search(self, state: ManagerChatState, arguments: dict[str, Any]) -> tuple[str, str]:
        query = str(arguments.get("query") or "").strip() or state["user_message"]
        try:
            n_results = int(arguments.get("n_results") or 3)
        except (TypeError, ValueError):
            n_results = 3
        n_results = max(1, min(n_results, 8))

        try:
            if hasattr(self.deps.rag_service, "search"):
                rag_context = self.deps.rag_service.search(query, n_results=n_results)
            else:
                rag_context = self.deps.rag_service.retrieve(query, state.get("context"))
        except Exception as exc:
            observation = f"memory_search failed: {type(exc).__name__}: {exc}"
            state["warnings"].append(observation)
            return observation, "warning"

        if rag_context:
            # Keep the raw memory text for specialists / memory answers.
            existing = state.get("rag_context")
            state["rag_context"] = f"{existing}\n{rag_context}".strip() if existing else rag_context
            state["rag_needed"] = True
            lines = [line for line in rag_context.splitlines() if line.strip()]
            return f"Retrieved {len(lines)} memory item(s). Summary: {rag_context[:240]}", "success"
        return "memory_search returned no results.", "warning"

    def _keyword_fallback(
        self,
        state: ManagerChatState,
        started_at: datetime,
        reason: str,
    ) -> ManagerChatState:
        rag_needed = self.deps.rag_service.is_needed(state["user_message"])
        state["rag_needed"] = rag_needed
        if not rag_needed:
            observation = f"{reason}. Keyword fallback skipped retrieval."
            self.recorder.step(
                state,
                "rag_react_node",
                "Fell back to keyword RAG gate.",
                "skip_memory_search",
                observation,
                "skipped",
            )
            self.recorder.log(
                state,
                agent="manager_agent",
                status="skipped",
                step="rag_react_fallback",
                started_at=started_at,
                thought="Fell back to keyword RAG gate.",
                observation=observation,
            )
            return state

        try:
            if hasattr(self.deps.rag_service, "search"):
                rag_context = self.deps.rag_service.search(state["user_message"])
            else:
                rag_context = self.deps.rag_service.retrieve(state["user_message"], state.get("context"))
            state["rag_context"] = rag_context or None
            if rag_context:
                observation = f"Keyword fallback retrieved memory. Summary: {rag_context[:240]}"
                status = "success"
            else:
                observation = "Keyword fallback found no memory context."
                status = "warning"
                state["warnings"].append(observation)
        except Exception as exc:
            observation = f"Keyword fallback failed: {type(exc).__name__}: {exc}"
            status = "warning"
            state["rag_context"] = None
            state["warnings"].append(observation)

        self.recorder.step(
            state,
            "rag_react_node",
            "Fell back to keyword RAG retrieval.",
            "call_memory_search",
            observation,
            status,
        )
        self.recorder.log(
            state,
            agent="manager_agent",
            status="success" if status == "success" else "skipped",
            step="rag_react_fallback",
            started_at=started_at,
            tool_called="mcp_memory_search",
            thought="Fell back to keyword RAG retrieval.",
            observation=observation,
            output_summary=observation[:300],
        )
        return state

    @staticmethod
    def _user_prompt(state: ManagerChatState) -> str:
        post = state.get("post") or {}
        brief = {
            "topic": post.get("topic"),
            "platform": post.get("platform"),
            "target_audience": post.get("target_audience"),
            "tone_of_voice": post.get("tone_of_voice"),
            "additional_context": post.get("additional_context"),
        }
        intent = state.get("intent") or "unknown"
        return (
            f"User message:\n{state['user_message']}\n\n"
            f"Intent: {intent}\n"
            f"Brief snapshot:\n{json.dumps(brief, ensure_ascii=False)}\n\n"
            "Decide whether to call memory_search."
        )

    # Backward-compatible aliases used by older docs/tests if imported directly.
    def rag_decision_node(self, state: ManagerChatState) -> ManagerChatState:
        return self.rag_react_node(state)

    def rag_retrieval_node(self, state: ManagerChatState) -> ManagerChatState:
        return state
