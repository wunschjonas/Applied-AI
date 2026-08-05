from __future__ import annotations

from datetime import datetime
from typing import Any

from app.graphs.dependencies import GraphDependencies, StepRecorder
from app.graphs.state import ManagerChatState
from app.graphs.support import post_fields
from app.graphs.support.delegation import build_execution_plan
from app.graphs.support.tao_composer import TaoEvent
from app.metrics import inc_manager_chat_intent

ROUTE_TARGETS = {
    "text_only": "TextAgent",
    "image_only": "ImageAgent",
    "text_and_image": "TextAgent, danach ImageAgent",
    "memory_inquiry": "Memory-Antwort aus RAG",
    "web_inquiry": "Web-Antwort aus Suche",
    "post_status_inquiry": "Post-Status aus posts.json",
    "clarification_needed": "Klärungsfrage",
}


class PlanningNodes:
    def __init__(self, deps: GraphDependencies):
        self.deps = deps
        self.recorder = StepRecorder(deps)

    def classify_intent_node(self, state: ManagerChatState) -> ManagerChatState:
        started_at = datetime.utcnow()
        intent = self.deps.intent_classifier.classify_intent(
            state["user_message"],
            post=state.get("post"),
        )
        state["intent"] = intent.label
        status = "needs_input" if intent.needs_clarification else "success"
        inc_manager_chat_intent(intent.label)

        event = TaoEvent(
            phase="classify_intent",
            node="classify_intent_node",
            agent="classify_intent_node",
            status=status,
            intent=intent.label,
            facts={"decision": intent.decision, "detail": intent.observation},
        )
        self.recorder.record(state, event)
        self.recorder.log(
            state,
            agent="manager_agent",
            status=status,
            step="classify_intent",
            started_at=started_at,
            event=event,
            output_summary=f"Intent: {intent.label}",
        )
        return state

    def create_plan_node(self, state: ManagerChatState) -> ManagerChatState:
        plan = build_execution_plan(
            intent=state["intent"],
            message=state["user_message"],
            context=self._brief_context(state),
            platform=state.get("platform"),
        )
        state["execution_plan"] = plan

        self.recorder.record(
            state,
            TaoEvent(
                phase="create_plan",
                node="create_plan_node",
                agent="create_plan_node",
                intent=state.get("intent"),
                facts={
                    "required_agents": plan.get("required_agents"),
                    "expected_artifacts": plan.get("expected_artifacts"),
                    "needs_rag_check": plan.get("needs_rag_check"),
                },
            ),
        )
        return state

    def _brief_context(self, state: ManagerChatState) -> Any:
        """Stored post fields as brief base; a context sent with this request wins over them."""
        post = state.get("post")
        if not post:
            return state.get("context")

        merged = post_fields.brief_context(post)
        request_context = state.get("context")
        if isinstance(request_context, dict):
            merged.update({key: value for key, value in request_context.items() if value})
        return merged

    def route_by_intent_node(self, state: ManagerChatState) -> ManagerChatState:
        intent = state["intent"]
        self.recorder.record(
            state,
            TaoEvent(
                phase="route_by_intent",
                node="route_by_intent",
                agent="route_by_intent",
                intent=intent,
                facts={"route_target": ROUTE_TARGETS.get(intent, "unbekannt")},
            ),
        )
        return state
