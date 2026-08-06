from __future__ import annotations

from app.graphs.dependencies import GraphDependencies, StepRecorder
from app.graphs.state import ManagerChatState
from app.graphs.support import post_data_llm, messages
from app.graphs.support.tao_composer import TaoEvent
from app.graphs.support.validation import ArtifactValidator
from app.metrics import inc_manager_validation

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
            text_length=(state.get("post") or {}).get("text_length"),
        )
        result = self.validator.decide(
            feedback=feedback,
            artifacts=state["generated_artifacts"],
            text_retry_count=state["text_retry_count"],
            image_retry_count=state["image_retry_count"],
        )
        state["validation_feedback"] = feedback
        state["validation_result"] = result
        if result == "retry_text":
            state["text_retry_count"] = state["text_retry_count"] + 1
        elif result == "retry_image":
            state["image_retry_count"] = state["image_retry_count"] + 1
        if result in VALIDATION_STATUS:
            state["status"] = VALIDATION_STATUS[result]
        inc_manager_validation(result)

        self.recorder.record(
            state,
            TaoEvent(
                phase="validate",
                node="validation_node",
                agent="validation_node",
                status="success" if result == "valid" else result,
                intent=state.get("intent"),
                facts={
                    "validation_result": result,
                    "feedback_keys": list(feedback.keys()) if isinstance(feedback, dict) else [],
                    "text_retry_count": state["text_retry_count"],
                    "image_retry_count": state["image_retry_count"],
                },
            ),
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
            detail = "Klärungsantwort beibehalten."
        elif intent == "memory_inquiry":
            detail = "Memory-Antwort beibehalten."
        elif intent == "memory_store" or artifacts.get("memory_store_ack"):
            detail = "Memory-Speicher-Bestätigung beibehalten."
        elif intent == "web_inquiry" or artifacts.get("web_answer"):
            detail = "Web-Suchantwort beibehalten."
        elif intent == "post_status_inquiry":
            detail = "Post-Status-Antwort beibehalten."
        elif state["status"] == "error":
            if text_ok or image_prompt_only or image_ok:
                state["status"] = "partial_success"
                fallback = messages.partial_message(text_ok, image_ok, image_prompt_only)
                detail = "Teilantwort nach Validierungsfehler."
            else:
                fallback = messages.WORKFLOW_FAILED
                detail = "Fehlerantwort zusammengestellt."
            state["assistant_message"] = self._compose(state, fallback, detail)
        elif intent == "text_only":
            fallback = messages.TEXT_SUCCESS
            detail = "Text-Erfolg zusammengestellt."
            state["assistant_message"] = self._compose(state, fallback, detail)
        elif intent == "image_only":
            if image_ok:
                fallback = messages.IMAGE_SUCCESS
                detail = "Bild-Erfolg zusammengestellt."
            else:
                state["status"] = "partial_success"
                fallback = messages.IMAGE_PROMPT_ONLY
                detail = "Nur Bildprompt — Teilerfolg."
            state["assistant_message"] = self._compose(state, fallback, detail)
        elif intent == "text_and_image":
            if text_ok and image_ok:
                fallback = messages.COMBINED_SUCCESS
                detail = "Text und Bild erfolgreich kombiniert."
            else:
                state["status"] = "partial_success"
                fallback = messages.partial_message(text_ok, image_ok, image_prompt_only)
                detail = "Kombinierte Teilantwort."
            state["assistant_message"] = self._compose(state, fallback, detail)
        else:
            fallback = messages.WORKFLOW_UNCLEAR
            detail = "Fallback-Antwort."
            state["assistant_message"] = self._compose(state, fallback, detail)

        self.recorder.record(
            state,
            TaoEvent(
                phase="assemble",
                node="assemble_response_node",
                agent="assemble_response_node",
                status=state.get("status", "success"),
                intent=intent,
                facts={"detail": detail},
            ),
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
        return post_data_llm.compose_manager_reply(
            hf=post_data_llm.try_hf(self.deps.hf_factory),
            fallback=fallback,
            situation=situation,
            user_message=state["user_message"],
            post=state.get("post"),
            artifact_summary=artifact_summary,
        )
