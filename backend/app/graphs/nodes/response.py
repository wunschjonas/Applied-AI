from __future__ import annotations

from app.graphs.dependencies import GraphDependencies, StepRecorder
from app.graphs.state import ManagerChatState
from app.graphs.support import brief_llm, messages
from app.graphs.support.validation import ArtifactValidator

VALIDATION_STATUS = {
    "valid": "success",
    "partial_success": "partial_success",
    "failed": "error",
    "retry_text": "retrying",
    "retry_image": "retrying",
}


class ResponseNodes:
    def __init__(self, deps: GraphDependencies):
        self.deps = deps
        self.recorder = StepRecorder(deps)
        self.validator = ArtifactValidator(deps.image_storage)

    def validation_node(self, state: ManagerChatState) -> ManagerChatState:
        feedback = self.validator.collect_feedback(
            intent=state["intent"],
            artifacts=state["generated_artifacts"],
            platform=state.get("platform"),
            assistant_message=state.get("assistant_message"),
        )
        result = self.validator.decide(
            feedback=feedback,
            artifacts=state["generated_artifacts"],
            text_retry_count=state["text_retry_count"],
            image_retry_count=state["image_retry_count"],
        )
        state["validation_feedback"] = feedback
        state["validation_result"] = result
        # Increment here (not in the router) so LangGraph persists the retry budget.
        if result == "retry_text":
            state["text_retry_count"] = state["text_retry_count"] + 1
        elif result == "retry_image":
            state["image_retry_count"] = state["image_retry_count"] + 1
        if result in VALIDATION_STATUS:
            state["status"] = VALIDATION_STATUS[result]

        self.recorder.step(
            state,
            "validation_node",
            f"Validation result: {result}.",
            "validate_results",
            str(
                {
                    "feedback": feedback,
                    "text_retry_count": state["text_retry_count"],
                    "image_retry_count": state["image_retry_count"],
                }
            ),
            "success" if result == "valid" else result,
        )
        return state

    def assemble_response_node(self, state: ManagerChatState) -> ManagerChatState:
        artifacts = state["generated_artifacts"]
        intent = state["intent"]
        image = artifacts.get("image") or {}
        text_ok = bool((artifacts.get("text") or {}).get("generated_text"))
        image_ok = self.validator.image_file_available(image)
        image_prompt_only = bool(image.get("image_prompt")) and not image_ok

        if intent == "clarification_needed":
            observation = "Clarification response kept."
        elif intent == "memory_inquiry":
            observation = "Memory inquiry response kept."
        elif intent == "post_status_inquiry":
            observation = "Post status response kept."
        elif state["status"] == "error":
            if text_ok or image_prompt_only or image_ok:
                state["status"] = "partial_success"
                fallback = messages.partial_message(text_ok, image_ok, image_prompt_only)
                observation = "Partial response assembled after validation failure."
            else:
                fallback = messages.WORKFLOW_FAILED
                observation = "Failure response assembled."
            state["assistant_message"] = self._compose(state, fallback, observation)
        elif intent == "text_only":
            fallback = messages.TEXT_SUCCESS
            observation = "Text-only success response assembled."
            state["assistant_message"] = self._compose(state, fallback, observation)
        elif intent == "image_only":
            if image_ok:
                fallback = messages.IMAGE_SUCCESS
                observation = "Image-only success response assembled."
            else:
                state["status"] = "partial_success"
                fallback = messages.IMAGE_PROMPT_ONLY
                observation = "Image prompt-only partial success response assembled."
            state["assistant_message"] = self._compose(state, fallback, observation)
        elif intent == "text_and_image":
            if text_ok and image_ok:
                fallback = messages.COMBINED_SUCCESS
                observation = "Combined success response assembled."
            else:
                state["status"] = "partial_success"
                fallback = messages.partial_message(text_ok, image_ok, image_prompt_only)
                observation = "Combined partial response assembled."
            state["assistant_message"] = self._compose(state, fallback, observation)
        else:
            fallback = messages.WORKFLOW_UNCLEAR
            observation = "Fallback response assembled."
            state["assistant_message"] = self._compose(state, fallback, observation)

        self.recorder.step(
            state,
            "assemble_response_node",
            "Final chat response assembled from actual graph artifacts.",
            "assemble_response",
            observation,
            state.get("status", "success"),
        )
        return state

    def _compose(self, state: ManagerChatState, fallback: str, situation: str) -> str:
        artifacts = state.get("generated_artifacts") or {}
        text_len = len((artifacts.get("text") or {}).get("generated_text") or "")
        image = artifacts.get("image") or {}
        artifact_summary = (
            f"text_chars={text_len}; image_url={image.get('image_url')}; "
            f"used_agents={state.get('used_agents')}"
        )
        return brief_llm.compose_manager_reply(
            hf=brief_llm.try_hf(self.deps.hf_factory),
            fallback=fallback,
            situation=situation,
            user_message=state["user_message"],
            post=state.get("post"),
            brief_updates=state.get("brief_updates"),
            artifact_summary=artifact_summary,
        )
