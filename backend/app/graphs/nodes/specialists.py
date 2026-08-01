from __future__ import annotations

from datetime import datetime
from typing import Any

from app.agents.image_agent import ImageAgent
from app.agents.text_agent import TextAgent
from app.graphs.dependencies import GraphDependencies, StepRecorder
from app.graphs.state import ManagerChatState
from app.graphs.support import brief_llm, messages
from app.graphs.support.delegation import context_value, image_task_with_marketing_text


class SpecialistNodes:
    def __init__(self, deps: GraphDependencies):
        self.deps = deps
        self.recorder = StepRecorder(deps)

    def text_agent_node(self, state: ManagerChatState) -> ManagerChatState:
        started_at = datetime.utcnow()
        assignment = self._assignment(state, "text")
        context = state.get("context")
        try:
            result = TextAgent(self.deps.hf_factory(), self.deps.trace_service).generate(
                task=assignment.get("task") or state["user_message"],
                trace=state["trace"],
                platform=assignment.get("platform", state.get("platform")),
                tone=assignment.get("tone", context_value(context, "tone", "professional")),
                target_audience=assignment.get("target_audience", context_value(context, "target_audience")),
                context=context,
                rag_context=state.get("rag_context"),
                validation_feedback=state.get("validation_feedback", {}).get("text"),
            )
        except Exception as exc:
            self._record_failure(state, "text", started_at, state["text_retry_count"], exc)
            return state

        state["generated_artifacts"]["text"] = result
        self._remember_agent(state, "TextAgent")
        self._save_specialist_chat(state, "text_agent", "Text artifact generated.", "text")
        self.recorder.step(
            state,
            "text_agent_node",
            "TextAgent completed successfully.",
            "call_text_agent",
            "Text artifact stored in graph state.",
        )
        self.recorder.log(
            state,
            agent="text_agent",
            status="success",
            step="generate_text",
            started_at=started_at,
            tool_called="huggingface_generate_text",
            thought=f"graph_node=text_agent_node; retry_count={state['text_retry_count']}",
            observation="Text artifact stored in graph state.",
            output_summary=f"{len(result.get('generated_text', ''))} chars, {len(result.get('hashtags', []))} hashtags",
        )
        return state

    def image_agent_node(self, state: ManagerChatState) -> ManagerChatState:
        started_at = datetime.utcnow()
        assignment = self._assignment(state, "image")
        context = state.get("context")
        marketing_text = (state["generated_artifacts"].get("text") or {}).get("generated_text")
        task = image_task_with_marketing_text(
            assignment.get("task") or state["user_message"],
            marketing_text,
        )
        try:
            result = ImageAgent(
                self.deps.hf_factory(),
                self.deps.trace_service,
                image_storage=self.deps.image_storage,
            ).generate_image(
                task=task,
                trace=state["trace"],
                platform=assignment.get("platform", state.get("platform")),
                visual_style=assignment.get("visual_style", context_value(context, "visual_style")),
                context=context,
                rag_context=state.get("rag_context"),
                validation_feedback=state.get("validation_feedback", {}).get("image"),
                post_id=state["post_id"],
            )
        except Exception as exc:
            self._record_failure(state, "image", started_at, state["image_retry_count"], exc)
            return state

        state["generated_artifacts"]["image"] = result
        self._remember_agent(state, "ImageAgent")
        status = "partial_success" if result.get("partial_success") else "success"
        summary = self._image_summary(result)
        self._save_specialist_chat(state, "image_agent", "Image artifact generated.", "image")
        self.recorder.step(
            state,
            "image_agent_node",
            "ImageAgent completed with image artifact."
            if status == "success"
            else "ImageAgent returned prompt-only partial success.",
            "call_image_agent",
            summary,
            status,
        )
        self.recorder.log(
            state,
            agent="image_agent",
            status="success" if status == "success" else "error",
            step="generate_image",
            started_at=started_at,
            tool_called="huggingface_text_to_image",
            thought=f"graph_node=image_agent_node; retry_count={state['image_retry_count']}",
            observation=summary,
            output_summary=summary,
        )
        return state

    def clarification_node(self, state: ManagerChatState) -> ManagerChatState:
        started_at = datetime.utcnow()
        state["assistant_message"] = brief_llm.compose_manager_reply(
            hf=brief_llm.try_hf(self.deps.hf_factory),
            fallback=messages.CLARIFICATION_REQUEST,
            situation="Intent is unclear. Ask whether the user wants text, image, or both, and invite brief details.",
            user_message=state["user_message"],
            post=state.get("post"),
            brief_updates=state.get("brief_updates"),
        )
        state["status"] = "needs_input"

        self.recorder.step(
            state,
            "clarification_node",
            "The request is unclear.",
            "ask_clarification",
            "No specialist agent or HuggingFace call was made.",
            "needs_input",
        )
        self.recorder.log(
            state,
            agent="manager_agent",
            status="skipped",
            step="ask_clarification",
            started_at=started_at,
            thought="Intent unclear - asked user for text/image/both + platform/audience/tone",
            observation="No specialist agent or HuggingFace call was made.",
        )
        return state

    def _assignment(self, state: ManagerChatState, artifact_type: str) -> dict[str, Any]:
        assignments = state.get("execution_plan", {}).get("assignments", {})
        return assignments.get(artifact_type) or {}

    def _record_failure(
        self,
        state: ManagerChatState,
        artifact_type: str,
        started_at: datetime,
        retry_count: int,
        exc: Exception,
    ) -> None:
        error = f"{type(exc).__name__}: {exc}"
        state["errors"].append(error)
        state["status"] = "error"
        is_text = artifact_type == "text"
        node = f"{artifact_type}_agent_node"

        self.recorder.step(
            state,
            node,
            f"{'TextAgent' if is_text else 'ImageAgent'} failed.",
            f"call_{artifact_type}_agent",
            error,
            "error",
        )
        self.recorder.log(
            state,
            agent=f"{artifact_type}_agent",
            status="error",
            step=f"generate_{artifact_type}",
            started_at=started_at,
            tool_called="huggingface_generate_text" if is_text else "huggingface_text_to_image",
            thought=f"graph_node={node}; retry_count={retry_count}",
            observation=error,
            output_summary=error,
        )

    def _save_specialist_chat(
        self,
        state: ManagerChatState,
        agent: str,
        assistant_message: str,
        artifact_type: str,
    ) -> None:
        chat = self.deps.chat_service.get_or_create_chat(state["post_id"], agent=agent)
        self.deps.chat_service.add_message(chat, "USER", state["user_message"])
        self.deps.chat_service.add_message(chat, "AGENT", assistant_message)

    def _remember_agent(self, state: ManagerChatState, agent: str) -> None:
        if agent not in state["used_agents"]:
            state["used_agents"].append(agent)

    def _image_summary(self, artifact: dict[str, Any]) -> str:
        if artifact.get("image_url"):
            return f"Image prompt and file ready: {artifact.get('image_filename')} -> {artifact.get('image_url')}"
        return f"Prompt ready but image unavailable: {artifact.get('image_error', 'unknown error')}"
