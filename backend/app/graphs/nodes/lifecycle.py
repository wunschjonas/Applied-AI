from __future__ import annotations

from app.graphs.dependencies import GraphDependencies, StepRecorder
from app.graphs.state import ManagerChatState
from app.graphs.support.delegation import resolve_platform
from app.graphs.support.tao_composer import TaoEvent


class LifecycleNodes:
    def __init__(self, deps: GraphDependencies):
        self.deps = deps
        self.recorder = StepRecorder(deps)

    def init_state_node(self, state: ManagerChatState) -> ManagerChatState:
        post_id = state["post_id"]
        chat = self.deps.chat_service.get_or_create_chat(post_id, agent="manager_agent")
        trace = self.deps.trace_service.create_trace(
            chat_id=chat["id"],
            metadata={"entrypoint": "manager_chat_langgraph", "graph": "ManagerChatGraph", "post_id": post_id},
        )
        context = state.get("context")
        message = state["user_message"].strip()

        new_state: ManagerChatState = {
            **state,
            "post_id": post_id,
            "chat": chat,
            "chat_id": chat["id"],
            "trace": trace,
            "trace_id": trace["trace_id"],
            "user_message": message,
            "context": context,
            "intent": "unclassified",
            "rag_needed": False,
            "rag_context": None,
            "used_agents": [],
            "generated_artifacts": {},
            "assistant_message": "",
            "trace_steps": [],
            "errors": [],
            "warnings": [],
            "status": "running",
            "platform": resolve_platform(context, message),
            "text_retry_count": 0,
            "image_retry_count": 0,
            "validation_feedback": {},
            "validation_result": "pending",
            "execution_plan": {},
            "post": None,
            "post_data_updates": {},
            "post_data_missing": [],
            "post_data_blocking": [],
            "explicit_generate": False,
            "brief_just_completed": False,
            "auto_generate": False,
            "force_generation": bool(state.get("force_generation")),
            "forced_intent": state.get("forced_intent"),
            "generation_pending": False,
            "followup_question": None,
            "tools_called": [],
            "post_data_checked": False,
            "post_data_complete": None,
            "post_data_incomplete_from_tool": False,
            "web_context": None,
            "tool_safety_blocked": False,
            "stored_preview": None,
            "stored_tags": [],
        }

        self.recorder.record(
            new_state,
            TaoEvent(
                phase="init_state",
                node="init_state_node",
                agent="init_state_node",
                facts={
                    "chat_id": chat["id"],
                    "trace_id": trace["trace_id"],
                    "platform": new_state["platform"],
                },
            ),
        )
        return new_state

    def save_trace_node(self, state: ManagerChatState) -> ManagerChatState:
        image = state["generated_artifacts"].get("image") or {}
        metadata = {
            "trace_id": state["trace_id"],
            "used_agents": state["used_agents"],
            "graph_node": "save_trace_node",
            "artifact_types": list(state["generated_artifacts"].keys()),
            "status": state["status"],
            "image_filename": image.get("image_filename"),
            "image_url": image.get("image_url"),
            "retry_count": {"text": state["text_retry_count"], "image": state["image_retry_count"]},
        }

        # Generate follow-up must not inject a synthetic USER line into the chat.
        if not state.get("force_generation"):
            self.deps.chat_service.add_message(state["chat"], "USER", state["user_message"])
        if state.get("assistant_message"):
            self.deps.chat_service.add_message(state["chat"], "AGENT", state["assistant_message"])
        state["trace"]["metadata"].update(metadata)
        self.deps.trace_service.store.save(state["trace"])

        self.recorder.record(
            state,
            TaoEvent(
                phase="save_trace",
                node="save_trace_node",
                agent="save_trace_node",
                status=state.get("status", "success"),
                intent=state.get("intent"),
                facts={
                    "chat_id": state["chat_id"],
                    "trace_id": state["trace_id"],
                    "used_agents": state["used_agents"],
                },
            ),
        )
        self.deps.trace_service.print_run_footer(state["trace"], state.get("status", "success"))
        return state
