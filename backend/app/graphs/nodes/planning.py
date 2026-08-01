from __future__ import annotations

from datetime import datetime
from typing import Any

from app.graphs.dependencies import GraphDependencies, StepRecorder
from app.graphs.state import ManagerChatState
from app.graphs.support import post_fields
from app.graphs.support.delegation import build_execution_plan

ROUTE_OBSERVATIONS = {
    "text_only": "Route to TextAgent.",
    "image_only": "Route to ImageAgent.",
    "text_and_image": "Route to TextAgent first, then ImageAgent.",
    "memory_inquiry": "Route to memory answer from RAG context.",
    "clarification_needed": "Route to clarification response.",
}


class PlanningNodes:
    def __init__(self, deps: GraphDependencies):
        self.deps = deps
        self.recorder = StepRecorder(deps)

    def classify_intent_node(self, state: ManagerChatState) -> ManagerChatState:
        started_at = datetime.utcnow()
        intent = self.deps.intent_classifier.classify_intent(state["user_message"])
        state["intent"] = intent.label
        status = "needs_input" if intent.needs_clarification else "success"

        self.recorder.step(
            state, "classify_intent_node", intent.decision, "classify_intent", intent.observation, status
        )
        self.recorder.log(
            state,
            agent="manager_agent",
            status=status,
            step="classify_intent",
            started_at=started_at,
            thought=f"{intent.label} - {intent.observation}",
            observation=intent.observation,
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

        self.recorder.step(
            state,
            "create_plan_node",
            "Created high-level execution plan.",
            "create_plan",
            str(plan),
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
        observation = ROUTE_OBSERVATIONS.get(state["intent"], "Unknown intent.")
        self.recorder.step(
            state,
            "route_by_intent",
            f"Routing selected for intent={state['intent']}.",
            "route_by_intent",
            observation,
        )
        return state
