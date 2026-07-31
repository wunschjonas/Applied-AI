from __future__ import annotations

from app.graphs.dependencies import GraphDependencies, StepRecorder
from app.graphs.state import ManagerChatState
from app.graphs.support.delegation import resolve_platform


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
            "brief_updates": {},
            "brief_missing": [],
            "brief_blocking": [],
            "explicit_generate": False,
            "followup_question": None,
        }

        self.recorder.step(
            new_state,
            "init_state_node",
            "Initialized Manager chat graph state.",
            "init_state",
            f"chat_id={chat['id']}; trace_id={trace['trace_id']}; platform={new_state['platform'] or 'unspecified'}.",
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

        self.deps.chat_service.add_message(
            state["chat"],
            "USER",
            state["user_message"],
            {"context": state.get("context") or {}, "trace_id": state["trace_id"]},
        )
        self.deps.chat_service.add_message(state["chat"], "AGENT", state["assistant_message"], metadata)
        state["trace"]["metadata"].update(metadata)
        self.deps.trace_service.store.save(state["trace"])

        self.recorder.step(
            state,
            "save_trace_node",
            "Chat messages, trace metadata and specialist logs are saved.",
            "persist_chat_trace_and_logs",
            f"Saved chat {state['chat_id']} with trace {state['trace_id']}.",
            state.get("status", "success"),
        )
        return state
