from __future__ import annotations

from app.graphs.dependencies import GraphDependencies, StepRecorder
from app.graphs.state import ManagerChatState
from app.graphs.support import messages
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
        elif state["status"] == "error":
            if text_ok or image_prompt_only or image_ok:
                state["status"] = "partial_success"
                state["assistant_message"] = messages.partial_message(text_ok, image_ok, image_prompt_only)
                observation = "Partial response assembled after validation failure."
            else:
                state["assistant_message"] = messages.WORKFLOW_FAILED
                observation = "Failure response assembled."
        elif intent == "text_only":
            state["assistant_message"] = messages.TEXT_SUCCESS
            observation = "Text-only success response assembled."
        elif intent == "image_only":
            if image_ok:
                state["assistant_message"] = messages.IMAGE_SUCCESS
                observation = "Image-only success response assembled."
            else:
                state["status"] = "partial_success"
                state["assistant_message"] = messages.IMAGE_PROMPT_ONLY
                observation = "Image prompt-only partial success response assembled."
        elif intent == "text_and_image":
            if text_ok and image_ok:
                state["assistant_message"] = messages.COMBINED_SUCCESS
                observation = "Combined success response assembled."
            else:
                state["status"] = "partial_success"
                state["assistant_message"] = messages.partial_message(text_ok, image_ok, image_prompt_only)
                observation = "Combined partial response assembled."
        else:
            state["assistant_message"] = messages.WORKFLOW_UNCLEAR
            observation = "Fallback response assembled."

        self.recorder.step(
            state,
            "assemble_response_node",
            "Final chat response assembled from actual graph artifacts.",
            "assemble_response",
            observation,
            state.get("status", "success"),
        )
        return state
