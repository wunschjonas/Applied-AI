from __future__ import annotations

from datetime import datetime

from app.graphs.dependencies import GraphDependencies, StepRecorder
from app.graphs.state import ManagerChatState
from app.graphs.support import post_data_llm, messages, post_fields
from app.graphs.support.post_fields import AWAITING_FIELD_KEY
from app.graphs.support.tao_composer import TaoEvent


class PostSyncNodes:
    """Keeps posts.json and the graph state in sync around a manager turn."""

    def __init__(self, deps: GraphDependencies):
        self.deps = deps
        self.recorder = StepRecorder(deps)

    def collect_post_data_node(self, state: ManagerChatState) -> ManagerChatState:
        started_at = datetime.utcnow()
        post = self.deps.post_repository.get(state["post_id"])
        state["explicit_generate"] = post_fields.wants_generation(state["user_message"])

        if not post:
            state["post"] = None
            state["post_data_updates"] = {}
            state["post_data_missing"] = []
            state["post_data_blocking"] = []
            state["brief_just_completed"] = False
            event = TaoEvent(
                phase="collect_post_data",
                node="collect_post_data_node",
                agent="collect_post_data_node",
                status="skipped",
                facts={"post_missing": True, "post_id": state["post_id"]},
            )
            self.recorder.record(state, event)
            return state

        missing_before = post_fields.missing_fields(post)
        hf = post_data_llm.try_hf(self.deps.hf_factory)
        updates = post_data_llm.extract_post_data_with_llm(state["user_message"], post, hf)
        if updates:
            post = self.deps.post_repository.update_fields(state["post_id"], updates) or post

        state["post"] = post
        state["post_data_updates"] = updates
        state["post_data_missing"] = post_fields.missing_fields(post)
        state["post_data_blocking"] = post_fields.missing_required_fields(post)
        state["brief_just_completed"] = bool(missing_before) and not state["post_data_missing"]

        if not state.get("platform"):
            state["platform"] = post.get("platform")

        event = TaoEvent(
            phase="collect_post_data",
            node="collect_post_data_node",
            agent="collect_post_data_node",
            status="success" if updates else "skipped",
            intent=state.get("intent"),
            facts={
                "updates": updates,
                "missing": state["post_data_missing"],
                "post_data_summary": post_fields.post_data_summary(post),
                "explicit_generate": state["explicit_generate"],
                "brief_just_completed": state["brief_just_completed"],
            },
        )
        self.recorder.record(state, event)
        self.recorder.log(
            state,
            agent="manager_agent",
            status="success",
            step="collect_post_brief",
            started_at=started_at,
            event=event,
            output_summary=post_fields.post_data_summary(post),
        )
        return state

    def context_question_node(self, state: ManagerChatState) -> ManagerChatState:
        started_at = datetime.utcnow()
        question = post_fields.next_question(state["post"] or {}, state.get("intent"))
        field, question_text = question if question else ("topic", post_fields.FIELD_QUESTIONS["topic"])

        fallback = messages.context_question(state["post_data_updates"], question_text)
        state["assistant_message"] = post_data_llm.compose_manager_reply(
            hf=post_data_llm.try_hf(self.deps.hf_factory),
            fallback=fallback,
            situation="Ask for the next missing Steckbrief field before generating.",
            user_message=state["user_message"],
            post=state.get("post"),
            post_data_updates=state.get("post_data_updates"),
            next_question=question_text,
        )
        state["status"] = "needs_input"
        state["followup_question"] = question_text
        self._set_awaiting_field(state["post_id"], field)

        event = TaoEvent(
            phase="ask_context",
            node="context_question_node",
            agent="context_question_node",
            status="needs_input",
            intent=state.get("intent"),
            facts={"field": field, "missing": state["post_data_missing"]},
        )
        self.recorder.record(state, event)
        self.recorder.log(
            state,
            agent="manager_agent",
            status="skipped",
            step="ask_post_context",
            started_at=started_at,
            event=event,
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

        self.recorder.record(
            state,
            TaoEvent(
                phase="persist_preview",
                node="persist_post_node",
                agent="persist_post_node",
                status=state.get("status", "success"),
                intent=state.get("intent"),
                facts={"preview_fields": sorted(patch.keys())},
            ),
        )

    def _append_followup(self, state: ManagerChatState) -> None:
        """Keep filling the brief over time: ask for one open field alongside the result."""
        if state.get("followup_question"):
            return

        if state.get("intent") in {
            "clarification_needed",
            "memory_inquiry",
            "memory_store",
            "post_status_inquiry",
            "web_inquiry",
        }:
            return

        # After a web research turn, do not nudge for Steckbrief fields in the same reply.
        if state.get("generated_artifacts", {}).get("web_answer"):
            return
        if "web_search" in (state.get("tools_called") or []) and state.get("web_context"):
            return

        question = post_fields.next_question(state["post"] or {}, state.get("intent"))
        if not question:
            self._set_awaiting_field(state["post_id"], None)
            return

        field, question_text = question
        state["followup_question"] = question_text
        followup = messages.followup_question(question_text)
        existing = (state.get("assistant_message") or "").strip()
        if followup.strip() and followup.strip() not in existing:
            state["assistant_message"] = f"{existing} {followup}".strip() if existing else followup
        self._set_awaiting_field(state["post_id"], field)

        self.recorder.record(
            state,
            TaoEvent(
                phase="followup",
                node="persist_post_node",
                agent="persist_post_node",
                status=state.get("status", "success"),
                intent=state.get("intent"),
                facts={"field": field, "missing": state["post_data_missing"]},
            ),
        )

    def _set_awaiting_field(self, post_id: str, field: str | None) -> None:
        self.deps.post_repository.update_fields(post_id, {AWAITING_FIELD_KEY: field})
