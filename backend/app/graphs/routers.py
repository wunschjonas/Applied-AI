from __future__ import annotations

from app.graphs.dependencies import GraphDependencies, StepRecorder
from app.graphs.state import ManagerChatState
from app.graphs.support import post_fields
from app.graphs.support.tao_composer import TaoEvent
from app.graphs.support.validation import ArtifactValidator
from app.metrics import inc_manager_chat_route

INTENT_ROUTES = {
    "text_only": "text_agent_node",
    "image_only": "image_agent_node",
    "text_and_image": "text_agent_node",
    "memory_inquiry": "memory_answer_node",
    "memory_store": "memory_store_ack_node",
    "web_inquiry": "web_answer_node",
    "post_status_inquiry": "post_status_node",
}

GENERATION_INTENTS = frozenset({"text_only", "image_only", "text_and_image"})


class GraphRouters:
    def __init__(self, deps: GraphDependencies):
        self.recorder = StepRecorder(deps)
        self.validator = ArtifactValidator(deps.image_storage)

    def intent_router(self, state: ManagerChatState) -> str:
        tools = state.get("tools_called") or []
        intent = state.get("intent")
        # Successful store wins — never answer as an empty memory search.
        if "memory_store" in tools and state.get("stored_preview"):
            target = "memory_store_ack_node"
        else:
            blocked = self._needs_post_data_first(state)
            if intent in GENERATION_INTENTS and not blocked:
                # A requested generation must not be swallowed by a tool hit —
                # rag_context / web_context stay available as briefing material.
                target = INTENT_ROUTES[intent]
            # Tool hits only win over clarification / post-data gate.
            elif "web_search" in tools and state.get("web_context"):
                target = "web_answer_node"
            elif (
                ("memory_search" in tools or "memory_list" in tools)
                and state.get("rag_context")
            ):
                target = "memory_answer_node"
            elif intent == "web_inquiry":
                target = "web_answer_node"
            elif intent == "memory_store":
                target = "memory_store_ack_node"
            elif intent == "memory_inquiry":
                target = "memory_answer_node"
            elif intent == "post_status_inquiry":
                target = "post_status_node"
            elif blocked:
                target = "context_question_node"
            else:
                target = INTENT_ROUTES.get(intent, "clarification_node")

        if target == "context_question_node" and state.get("tool_safety_blocked"):
            self._record_post_data_safety(state)
        inc_manager_chat_route(target)
        return target

    def _record_post_data_safety(self, state: ManagerChatState) -> None:
        blocking = state.get("post_data_blocking") or []
        self.recorder.record(
            state,
            TaoEvent(
                phase="post_data_safety",
                node="route_by_intent",
                agent="route_by_intent",
                status="needs_input",
                intent=state.get("intent"),
                facts={
                    "detail": "Safety: Steckbrief unvollständig, Generierung blockiert (Completeness-Tool übersprungen).",
                    "post_data_missing": list(blocking),
                },
            ),
        )

    def _needs_post_data_first(self, state: ManagerChatState) -> bool:
        """Ask for Steckbrief fields before generating.

        Primary signal: check_post_data_completeness tool result.
        Safety-net: blocking fields if tools skipped completeness.
        explicit_generate must NOT bypass incomplete required/image fields.
        """
        if state.get("intent") not in GENERATION_INTENTS:
            return False

        blocking = post_fields.missing_fields_for_intent(
            state.get("post") or {},
            state.get("intent"),
        )
        if blocking:
            state["post_data_blocking"] = list(blocking)

        # Tool result wins — incomplete brief must be clarified.
        if state.get("post_data_incomplete_from_tool"):
            return True

        # Safety-net when LLM skipped check_post_data_completeness
        if state.get("post") and blocking and not state.get("post_data_checked"):
            state["tool_safety_blocked"] = True
            return True

        if state.get("post_data_checked") and state.get("post_data_complete") is False:
            return True

        # Only allow explicit generate when nothing required is still open.
        if state.get("explicit_generate") and not blocking:
            return False

        return bool(blocking)

    def after_text_router(self, state: ManagerChatState) -> str:
        if state["intent"] != "text_and_image":
            return "validation_node"
        # On a text retry the image already exists; regenerating it would cost a
        # second run and could replace a valid image with a failed one.
        image = state["generated_artifacts"].get("image") or {}
        if self.validator.image_file_available(image):
            return "validation_node"
        return "image_agent_node"

    def retry_router(self, state: ManagerChatState) -> str:
        result = state.get("validation_result")
        if result == "retry_text":
            return self._record_retry(state, "text", "TextAgent")
        if result == "retry_image":
            return self._record_retry(state, "image", "ImageAgent")
        return "assemble_response_node"

    def _record_retry(self, state: ManagerChatState, artifact_type: str, agent_label: str) -> str:
        feedback = state.get("validation_feedback", {}).get(artifact_type)
        event = TaoEvent(
            phase="retry",
            node="validation_node",
            agent="validation_node",
            status=f"retry_{artifact_type}",
            intent=state.get("intent"),
            facts={
                "artifact_type": artifact_type,
                "agent_label": agent_label,
                "feedback": feedback,
                "detail": f"Validierung fehlgeschlagen — Retry {agent_label}.",
            },
        )
        self.recorder.record(state, event)
        self.recorder.log(
            state,
            agent=f"{artifact_type}_agent",
            status="skipped",
            step=f"retry_{artifact_type}",
            action="manager_chat_retry",
            event=event,
        )
        return f"{artifact_type}_agent_node"
