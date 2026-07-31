from __future__ import annotations

from app.graphs.dependencies import GraphDependencies, StepRecorder
from app.graphs.state import ManagerChatState

INTENT_ROUTES = {
    "text_only": "text_agent_node",
    "image_only": "image_agent_node",
    "text_and_image": "text_agent_node",
}


class GraphRouters:
    def __init__(self, deps: GraphDependencies):
        self.recorder = StepRecorder(deps)

    def maybe_rag_router(self, state: ManagerChatState) -> str:
        return "rag_retrieval_node" if state.get("rag_needed") else "route_by_intent"

    def intent_router(self, state: ManagerChatState) -> str:
        if self._needs_brief_first(state):
            return "context_question_node"
        return INTENT_ROUTES.get(state["intent"], "clarification_node")

    def _needs_brief_first(self, state: ManagerChatState) -> bool:
        """Ask for topic and platform before generating, unless the user explicitly ordered it."""
        if not state.get("post") or not state.get("brief_blocking"):
            return False
        return not state.get("explicit_generate")

    def after_text_router(self, state: ManagerChatState) -> str:
        return "image_agent_node" if state["intent"] == "text_and_image" else "validation_node"

    def retry_router(self, state: ManagerChatState) -> str:
        result = state.get("validation_result")
        if result == "retry_text" and state["text_retry_count"] == 0:
            state["text_retry_count"] += 1
            return self._record_retry(state, "text", "TextAgent")
        if result == "retry_image" and state["image_retry_count"] == 0:
            state["image_retry_count"] += 1
            return self._record_retry(state, "image", "ImageAgent")
        return "assemble_response_node"

    def _record_retry(self, state: ManagerChatState, artifact_type: str, agent_label: str) -> str:
        action = f"retry_{artifact_type}"
        feedback = str(state.get("validation_feedback", {}).get(artifact_type))

        self.recorder.step(state, "validation_node", f"Retrying {agent_label} once.", action, feedback, action)
        self.recorder.log(
            state,
            agent=f"{artifact_type}_agent",
            status="skipped",
            step=action,
            action="manager_chat_retry",
            decision=feedback,
        )
        return f"{artifact_type}_agent_node"
