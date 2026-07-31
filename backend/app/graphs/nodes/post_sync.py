from __future__ import annotations

from datetime import datetime

from app.graphs.dependencies import GraphDependencies, StepRecorder
from app.graphs.state import ManagerChatState
from app.graphs.support import messages, post_fields
from app.graphs.support.post_fields import AWAITING_FIELD_KEY


class PostSyncNodes:
    """Keeps posts.json and the graph state in sync around a manager turn."""

    def __init__(self, deps: GraphDependencies):
        self.deps = deps
        self.recorder = StepRecorder(deps)

    def collect_brief_node(self, state: ManagerChatState) -> ManagerChatState:
        started_at = datetime.utcnow()
        post = self.deps.post_repository.get(state["post_id"])
        state["explicit_generate"] = post_fields.wants_generation(state["user_message"])

        if not post:
            # Direct API or test usage without a stored post: nothing to brief.
            state["post"] = None
            state["brief_updates"] = {}
            state["brief_missing"] = []
            state["brief_blocking"] = []
            self.recorder.step(
                state,
                "collect_brief_node",
                "No stored post for this chat, briefing skipped.",
                "collect_post_brief",
                f"post_id={state['post_id']} not found in posts.json.",
                "skipped",
            )
            return state

        updates = post_fields.extract_fields(state["user_message"], post)
        if updates:
            post = self.deps.post_repository.update_fields(state["post_id"], updates) or post

        state["post"] = post
        state["brief_updates"] = updates
        state["brief_missing"] = post_fields.missing_fields(post)
        state["brief_blocking"] = post_fields.missing_required_fields(post)

        if not state.get("platform"):
            state["platform"] = post.get("platform")

        observation = f"Updated {updates or 'nothing'}. Brief now: {post_fields.brief_summary(post)}"
        self.recorder.step(
            state,
            "collect_brief_node",
            "Collected post brief fields from the chat message.",
            "collect_post_brief",
            observation,
            "success" if updates else "skipped",
        )
        self.recorder.log(
            state,
            agent="manager_agent",
            status="success",
            step="collect_post_brief",
            started_at=started_at,
            decision=f"explicit_generate={state['explicit_generate']}; missing={state['brief_missing']}",
            output_summary=observation,
        )
        return state

    def context_question_node(self, state: ManagerChatState) -> ManagerChatState:
        started_at = datetime.utcnow()
        question = post_fields.next_question(state["post"] or {})
        field, question_text = question if question else ("topic", post_fields.FIELD_QUESTIONS["topic"])

        state["assistant_message"] = messages.context_question(state["brief_updates"], question_text)
        state["status"] = "needs_input"
        state["followup_question"] = question_text
        self._set_awaiting_field(state["post_id"], field)

        self.recorder.step(
            state,
            "context_question_node",
            f"Asking for the missing post field '{field}' before delegating.",
            "ask_post_context",
            f"Still missing: {state['brief_missing']}. No specialist agent was called.",
            "needs_input",
        )
        self.recorder.log(
            state,
            agent="manager_agent",
            status="skipped",
            step="ask_post_context",
            started_at=started_at,
            decision=f"Missing required fields {state['brief_blocking']} - asked for '{field}'",
            output_summary=state["assistant_message"],
        )
        return state

    def persist_post_node(self, state: ManagerChatState) -> ManagerChatState:
        if not state.get("post"):
            return state

        self._store_preview(state)
        self._append_followup(state)
        return state

    def _store_preview(self, state: ManagerChatState) -> None:
        artifacts = state["generated_artifacts"]
        text = artifacts.get("text") or {}
        image = artifacts.get("image") or {}
        patch: dict[str, object] = {}

        if text.get("generated_text"):
            patch["generated_text"] = text["generated_text"]
            patch["hashtags"] = text.get("hashtags", [])
        if image.get("image_prompt"):
            patch["image_prompt_optional"] = image["image_prompt"]
        if image.get("image_url"):
            patch["image_url"] = image["image_url"]
            patch["image_filename"] = image.get("image_filename")

        if not patch:
            return

        patch["post_structure"] = {
            "manager_response": state["assistant_message"],
            "used_agents": state["used_agents"],
        }
        self.deps.post_repository.merge_preview(state["post_id"], patch)
        self.deps.post_repository.update_fields(state["post_id"], {"status": "preview_ready"})

        self.recorder.step(
            state,
            "persist_post_node",
            "Stored generated artifacts in the post preview.",
            "persist_post_preview",
            f"Preview fields updated: {sorted(patch.keys())}.",
            state.get("status", "success"),
        )

    def _append_followup(self, state: ManagerChatState) -> None:
        """Keep filling the brief over time: ask for one open field alongside the result."""
        if state.get("followup_question"):
            return  # context_question_node already asked; do not stack a second question.

        question = post_fields.next_question(state["post"] or {})
        if not question:
            self._set_awaiting_field(state["post_id"], None)
            return

        field, question_text = question
        state["followup_question"] = question_text
        state["assistant_message"] = f"{state['assistant_message']} {messages.followup_question(question_text)}"
        self._set_awaiting_field(state["post_id"], field)

        self.recorder.step(
            state,
            "persist_post_node",
            f"Appended a follow-up question for the open post field '{field}'.",
            "ask_post_followup",
            f"Still missing: {state['brief_missing']}.",
            state.get("status", "success"),
        )

    def _set_awaiting_field(self, post_id: str, field: str | None) -> None:
        self.deps.post_repository.update_fields(post_id, {AWAITING_FIELD_KEY: field})
